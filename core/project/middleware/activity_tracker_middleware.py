import json
import time

import rest_framework_simplejwt.exceptions
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import Resolver404, resolve
from django.utils import timezone
from rest_framework_simplejwt import authentication
from rest_framework_simplejwt.tokens import AccessToken

from drf_user_activity_tracker import ACTIVITY_TRACKER_SIGNAL
from drf_user_activity_tracker.start_logger_when_server_starts import LOGGER_THREAD
from drf_user_activity_tracker.utils import get_client_ip, get_headers, mask_sensitive_data

User = get_user_model()


class ActivityTrackerMiddleware:
    """
    Local safe version of drf_user_activity_tracker middleware.
    Key fix:
    - Do not assume every response has `response.data` (e.g. HttpResponseRedirect from OIDC).
    """

    def __init__(self, get_response):
        self.get_response = get_response

        self.DRF_ACTIVITY_TRACKER_DATABASE = getattr(settings, "DRF_ACTIVITY_TRACKER_DATABASE", False)
        self.DRF_ACTIVITY_TRACKER_SIGNAL = getattr(settings, "DRF_ACTIVITY_TRACKER_SIGNAL", False)

        self.DRF_ACTIVITY_TRACKER_PATH_TYPE = getattr(settings, "DRF_ACTIVITY_TRACKER_PATH_TYPE", "ABSOLUTE")
        if self.DRF_ACTIVITY_TRACKER_PATH_TYPE not in ["ABSOLUTE", "RAW_URI", "FULL_PATH"]:
            self.DRF_ACTIVITY_TRACKER_PATH_TYPE = "ABSOLUTE"

        self.DRF_ACTIVITY_TRACKER_SKIP_URL_NAME = ["history-list"]
        configured_skip_names = getattr(settings, "DRF_ACTIVITY_TRACKER_SKIP_URL_NAME", [])
        if isinstance(configured_skip_names, (tuple, list)):
            self.DRF_ACTIVITY_TRACKER_SKIP_URL_NAME.extend(configured_skip_names)

        self.DRF_ACTIVITY_TRACKER_SKIP_NAMESPACE = []
        configured_skip_ns = getattr(settings, "DRF_ACTIVITY_TRACKER_SKIP_NAMESPACE", [])
        if isinstance(configured_skip_ns, (tuple, list)):
            self.DRF_ACTIVITY_TRACKER_SKIP_NAMESPACE = configured_skip_ns

        self.DRF_ACTIVITY_TRACKER_METHODS = []
        configured_methods = getattr(settings, "DRF_ACTIVITY_TRACKER_METHODS", [])
        if isinstance(configured_methods, (tuple, list)):
            self.DRF_ACTIVITY_TRACKER_METHODS = configured_methods

    def __call__(self, request):
        if not (self.DRF_ACTIVITY_TRACKER_DATABASE or self.DRF_ACTIVITY_TRACKER_SIGNAL):
            return self.get_response(request)

        try:
            match = resolve(request.path)
            url_name = match.url_name
            namespace = match.namespace
        except Resolver404:
            return self.get_response(request)

        if namespace in ("admin", "oidc"):
            return self.get_response(request)
        if url_name in self.DRF_ACTIVITY_TRACKER_SKIP_URL_NAME:
            return self.get_response(request)
        if namespace in self.DRF_ACTIVITY_TRACKER_SKIP_NAMESPACE:
            return self.get_response(request)

        start_time = time.time()
        request_data = ""
        try:
            request_data = json.loads(request.body) if request.body else ""
        except Exception:
            pass

        response = self.get_response(request)

        header_token = request.META.get("HTTP_AUTHORIZATION")
        user = None

        if header_token:
            try:
                user = authentication.JWTAuthentication().authenticate(request)[0]
            except (rest_framework_simplejwt.exceptions.InvalidToken, TypeError, IndexError):
                user = request.user
        elif hasattr(response, "data") and isinstance(response.data, dict) and response.data.get("access"):
            try:
                user_token = AccessToken(response.data.get("access"))
                user = User.objects.get(id=user_token.get("user_id"))
            except Exception:
                user = request.user
        else:
            user = request.user

        if not user or user.is_anonymous:
            return response

        method = request.method
        if len(self.DRF_ACTIVITY_TRACKER_METHODS) > 0 and method not in self.DRF_ACTIVITY_TRACKER_METHODS:
            return response

        if response.get("content-type") not in ("application/json", "application/vnd.api+json"):
            return response

        if getattr(response, "streaming", False):
            response_body = "** Streaming **"
        else:
            try:
                if isinstance(response.content, bytes):
                    response_body = json.loads(response.content.decode())
                else:
                    response_body = json.loads(response.content)
            except Exception:
                return response

        if self.DRF_ACTIVITY_TRACKER_PATH_TYPE == "FULL_PATH":
            api = request.get_full_path()
        elif self.DRF_ACTIVITY_TRACKER_PATH_TYPE == "RAW_URI":
            api = request.get_raw_uri()
        else:
            api = request.build_absolute_uri()

        data = dict(
            url_name=url_name,
            url_path=request.path,
            user_id=user.id,
            api=api,
            headers=mask_sensitive_data(get_headers(request=request)),
            body=mask_sensitive_data(request_data),
            method=method,
            client_ip_address=get_client_ip(request),
            response=mask_sensitive_data(response_body),
            status_code=response.status_code,
            execution_time=time.time() - start_time,
            created_time=timezone.now(),
        )

        if self.DRF_ACTIVITY_TRACKER_DATABASE and LOGGER_THREAD:
            d = data.copy()
            d["headers"] = json.dumps(d["headers"], indent=4)
            if request_data:
                d["body"] = json.dumps(d["body"], indent=4)
            d["response"] = json.dumps(d["response"], indent=4)
            LOGGER_THREAD.put_log_data(data=d)

        if self.DRF_ACTIVITY_TRACKER_SIGNAL:
            ACTIVITY_TRACKER_SIGNAL.listen(**data)

        return response
