import socketio
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse

sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins="*"
)

@sio.event
async def connect(sid, environ):
    # Parse chat_id from query string
    query_string = environ.get("QUERY_STRING", "")
    params = dict(qc.split("=") for qc in query_string.split("&") if "=" in qc)
    chat_id = params.get("chat_id", sid) 
    room_id = f"chat_{chat_id}"

    await sio.save_session(sid, {"chat_id": chat_id, "room_id": room_id})
    await sio.enter_room(sid, room_id)

    await sio.emit("server_message", {"msg": f"Connected to room {room_id}"}, to=sid)


@sio.event
async def disconnect(sid):
    print(f"Client disconnected: {sid}")

async def stream_chunk(request):
    data = await request.json()
    chat_id = data["chat_id"]
    chunk = data["chunk"]

    room_id = f"chat_{chat_id}"

    # Emit to the room
    await sio.emit("bot_stream_chunk", {"chunk": chunk, "chat_id": chat_id}, room=room_id)
    return JSONResponse({"status": "ok"})


rest_routes = [
    Route("/stream_chunk", stream_chunk, methods=["POST"]),
]

rest_app = Starlette(routes=rest_routes)
app = socketio.ASGIApp(sio, other_asgi_app=rest_app)
