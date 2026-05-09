from flask import Flask, jsonify, redirect, request, Response, stream_with_context, send_file
from googleapiclient.discovery import build
from google.oauth2 import service_account
import time
import unicodedata
import requests

app = Flask(__name__)

# =========================================================
# CONFIGURACION PRINCIPAL
# =========================================================
YOUTUBE_CHANNEL_HANDLE = "primeraiglesiabautistahispana1"
YOUTUBE_CHANNEL_URL = f"https://www.youtube.com/@{YOUTUBE_CHANNEL_HANDLE}"
YOUTUBE_LIVE_URL = f"{YOUTUBE_CHANNEL_URL}/live"

# Fotos siguen saliendo de Google Drive para el slideshow de fondo.
CARPETAS_DRIVE = {
    "fotos": "1dFmpu9ycpP2-Cb5lvogHOEpy1Odw7Oe5"
}

FILE_JSON = "credenciales.json"
CACHE_SECONDS = 300  # 5 minutos
_youtube_cache = {"time": 0, "items": []}
_stream_cache = {}  # video_id/url -> {time, url, title}
STREAM_CACHE_SECONDS = 1800  # 30 minutos. Las URLs de YouTube expiran; no subir mucho este valor.

# Reglas para separar videos por titulo.
YOUTUBE_REGLAS = {
    "predicaciones": {
        "starts": ["servicio", "servicion"],
        "contains": []
    },
    "estudios": {
        "starts": [],
        "contains": ["estudio biblico", "estudios biblicos"]
    },
    "podcast": {
        "starts": ["espacios para la gracia", "espacio para la gracia"],
        "contains": []
    }
}


def normalizar(texto):
    texto = texto or ""
    texto = texto.lower().strip()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def conectar_drive():
    creds = service_account.Credentials.from_service_account_file(
        FILE_JSON, scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    return build("drive", "v3", credentials=creds)


def obtener_videos_youtube():
    """
    Lee videos publicos del canal con yt-dlp.
    No descarga videos; solo lee titulos e IDs.
    """
    ahora = time.time()
    if _youtube_cache["items"] and ahora - _youtube_cache["time"] < CACHE_SECONDS:
        return _youtube_cache["items"]

    import yt_dlp

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": True,
        "playlistend": 100,
        "ignoreerrors": True,
    }

    videos_url = f"{YOUTUBE_CHANNEL_URL}/videos"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(videos_url, download=False)

    entries = info.get("entries", []) if info else []
    items = []

    for entry in entries:
        if not entry:
            continue

        video_id = entry.get("id") or entry.get("url")
        title = entry.get("title") or "Video de YouTube"

        if not video_id:
            continue

        if "watch?v=" in video_id:
            video_id = video_id.split("watch?v=")[-1].split("&")[0]

        thumb = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        items.append({
            "id": video_id,
            "title": title,
            "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
            "thumbnail": thumb
        })

    _youtube_cache["time"] = ahora
    _youtube_cache["items"] = items
    return items


def filtrar_youtube_por_seccion(seccion):
    reglas = YOUTUBE_REGLAS.get(seccion)
    if not reglas:
        return []

    resultados = []
    for video in obtener_videos_youtube():
        titulo_norm = normalizar(video["title"])
        empieza = any(titulo_norm.startswith(normalizar(p)) for p in reglas["starts"])
        contiene = any(normalizar(p) in titulo_norm for p in reglas["contains"])
        if empieza or contiene:
            resultados.append(video)

    return resultados


def obtener_stream_youtube(youtube_url, cache_key=None, live=False):
    """
    Convierte YouTube a una URL que Roku pueda reproducir.

    IMPORTANTE:
    - Para videos grabados usamos MP4 progresivo H.264/AAC cuando existe.
      Es mucho mas estable en Roku que mandar el manifest HLS de YouTube.
    - Para EN VIVO usamos HLS porque un live no tiene MP4 progresivo.
    """
    import yt_dlp

    key = cache_key or youtube_url
    if live:
        key = f"live:{key}"

    ahora = time.time()
    cached = _stream_cache.get(key)
    if cached and ahora - cached["time"] < STREAM_CACHE_SECONDS:
        return cached

    # Videos normales: preferir MP4 progresivo compatible con Roku.
    # Live: preferir HLS.
    if live:
        format_selector = "best[protocol^=m3u8]/best"
    else:
        format_selector = (
            "best[protocol=https][ext=mp4][vcodec^=avc1][acodec^=mp4a]/"
            "best[protocol=https][ext=mp4][acodec!=none][vcodec!=none]/"
            "best[ext=mp4][acodec!=none][vcodec!=none]/"
            "best[protocol^=m3u8]/best"
        )

    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "format": format_selector,
        "noplaylist": True,
        "ignoreerrors": False,
        "geo_bypass": True,
        "http_headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
        },
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)

    if not info:
        raise RuntimeError("yt-dlp no devolvio informacion del video")

    stream_url = info.get("url")
    title = info.get("title") or "Video de YouTube"
    ext = (info.get("ext") or "").lower()
    protocol = (info.get("protocol") or "").lower()
    format_id = info.get("format_id") or ""

    if not stream_url:
        raise RuntimeError("yt-dlp no devolvio URL de stream")

    # Roku espera streamFormat: mp4 para video progresivo; hls para .m3u8/live.
    if live or "m3u8" in protocol or ".m3u8" in stream_url:
        stream_format = "hls"
    elif ext == "mp4" or ".mp4" in stream_url.split("?")[0].lower():
        stream_format = "mp4"
    else:
        stream_format = "mp4"

    print("YOUTUBE RESUELTO:", {
        "title": title,
        "format_id": format_id,
        "ext": ext,
        "protocol": protocol,
        "streamformat": stream_format,
        "url_preview": stream_url[:120],
    })

    result = {
        "time": ahora,
        "url": stream_url,
        "title": title,
        "streamformat": stream_format,
        "format_id": format_id,
        "ext": ext,
        "protocol": protocol,
    }
    _stream_cache[key] = result
    return result


@app.route("/feed/live")
def feed_live():
    """
    Para Roku: devuelve un item que primero se resuelve con /resolve/live.
    No devuelve el link YouTube directo.
    """
    return jsonify([{
        "title": "EN VIVO - YouTube",
        "url": request.host_url.rstrip("/") + "/resolve/live",
        "streamformat": "resolver",
        "hdposterurl": request.host_url.rstrip("/") + "/static/logo_hd.png",
        "sdposterurl": request.host_url.rstrip("/") + "/static/logo_hd.png"
    }])


@app.route("/feed/<seccion>")
def generar_feed(seccion):
    """
    Rutas del canal Roku:
    - /feed/predicaciones -> YouTube: titulos que empiezan con Servicio/Servicion
    - /feed/estudios      -> YouTube: titulos que contienen Estudio Biblico
    - /feed/podcast       -> YouTube: titulos que empiezan con Espacios para la Gracia
    - /feed/fotos         -> Google Drive: imagenes para slideshow
    - /feed/live          -> YouTube Live actual
    """

    if seccion in YOUTUBE_REGLAS:
        videos = filtrar_youtube_por_seccion(seccion)
        salida = []

        for video in videos:
            # Para videos grabados, Roku reproduce directo desde Flask.
            # El .mp4 en la URL ayuda a Roku a reconocer el tipo de medio y
            # evita que se quede en 0% antes de pedir el stream.
            proxy_url = request.host_url.rstrip("/") + f"/proxy/youtube/{video['id']}.mp4"
            salida.append({
                "title": video["title"],
                "url": proxy_url,
                "streamformat": "mp4",
                "contenttype": "movie",
                "hdposterurl": video.get("thumbnail", ""),
                "sdposterurl": video.get("thumbnail", "")
            })

        return jsonify(salida)

    if seccion == "fotos":
        id_carpeta = CARPETAS_DRIVE["fotos"]
        service = conectar_drive()
        query = f"'{id_carpeta}' in parents and (mimeType contains 'image/')"
        res = service.files().list(
            q=query,
            fields="files(id, name, mimeType)",
            orderBy="name"
        ).execute()

        archivos = res.get("files", [])
        lista_resultados = []

        for f in archivos:
            link_directo = f"https://drive.google.com/uc?export=download&id={f['id']}"
            lista_resultados.append({
                "title": f["name"],
                "url": link_directo,
                "streamformat": "mp4"
            })

        return jsonify(lista_resultados)

    return jsonify({"error": "Seccion no encontrada"}), 404


@app.route("/resolve/youtube/<video_id>")
def resolve_youtube(video_id):
    """
    Roku llama esta ruta al darle Play.

    IMPORTANTE:
    No le damos a Roku la URL googlevideo.com directa, porque muchas veces
    YouTube firma esa URL para la IP del servidor que la resolvio. Si Roku
    intenta abrirla desde otra IP/protocolo, se queda cargando en 0%.

    Por eso Roku reproduce desde /proxy/youtube/<video_id>, y Flask hace
    el puente hacia YouTube.
    """
    try:
        youtube_url = f"https://www.youtube.com/watch?v={video_id}"
        result = obtener_stream_youtube(youtube_url, cache_key=video_id, live=False)
        proxy_url = request.host_url.rstrip("/") + f"/proxy/youtube/{video_id}"
        return jsonify({
            "title": result["title"],
            "url": proxy_url,
            "streamformat": "mp4",
            "format_id": result.get("format_id", ""),
            "modo": "proxy"
        })
    except Exception as e:
        print("ERROR RESOLVIENDO VIDEO YOUTUBE:", str(e))
        return jsonify({"error": "No se pudo abrir este video de YouTube."}), 500


@app.route("/proxy/youtube/<video_id>.mp4")
@app.route("/proxy/youtube/<video_id>")
def proxy_youtube(video_id):
    """
    Proxy MP4 para Roku.
    Soporta Range requests, que Roku usa para empezar, adelantar y medir progreso.
    """
    try:
        result = obtener_stream_youtube(
            f"https://www.youtube.com/watch?v={video_id}",
            cache_key=video_id,
            live=False
        )
        upstream_url = result["url"]

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9,es;q=0.8",
            "Connection": "keep-alive",
        }

        # Roku normalmente manda Range: bytes=0-
        range_header = request.headers.get("Range")
        if range_header:
            headers["Range"] = range_header

        print("PROXY YOUTUBE:", {
            "video_id": video_id,
            "method": request.method,
            "range": range_header,
            "format_id": result.get("format_id"),
            "upstream_preview": upstream_url[:100],
        })

        upstream = requests.get(upstream_url, headers=headers, stream=True, timeout=30)

        response_headers = {
            "Content-Type": "video/mp4",
            "Accept-Ranges": upstream.headers.get("Accept-Ranges", "bytes"),
            "Cache-Control": "no-cache",
            "Content-Disposition": "inline; filename=video.mp4",
            "Access-Control-Allow-Origin": "*",
        }

        for h in ["Content-Length", "Content-Range"]:
            if h in upstream.headers:
                response_headers[h] = upstream.headers[h]

        status_code = upstream.status_code
        if status_code not in (200, 206):
            print("ERROR UPSTREAM YOUTUBE:", status_code, upstream.text[:300] if upstream.text else "")

        def generate():
            try:
                for chunk in upstream.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        yield chunk
            finally:
                upstream.close()

        return Response(
            stream_with_context(generate()),
            status=status_code,
            headers=response_headers,
            direct_passthrough=True
        )

    except Exception as e:
        print("ERROR EN PROXY YOUTUBE:", str(e))
        return "Error reproduciendo video de YouTube por proxy", 500


@app.route("/resolve/live")
def resolve_live():
    """
    Devuelve el stream HLS del live actual. Solo funciona cuando la iglesia esta en vivo.
    """
    try:
        result = obtener_stream_youtube(YOUTUBE_LIVE_URL, cache_key="live", live=True)
        return jsonify({
            "title": result["title"] or "EN VIVO - YouTube",
            "url": result["url"],
            "streamformat": "hls",
            "format_id": result.get("format_id", "")
        })
    except Exception as e:
        print("ERROR OBTENIENDO EN VIVO YOUTUBE:", str(e))
        return jsonify({"error": "No hay transmision en vivo ahora o YouTube no entrego el stream."}), 404


# Ruta vieja para pruebas en navegador. Roku ya no depende de redireccion.
@app.route("/stream/youtube/<video_id>")
def stream_youtube(video_id):
    try:
        result = obtener_stream_youtube(f"https://www.youtube.com/watch?v={video_id}", cache_key=video_id, live=False)
        return redirect(result["url"], code=302)
    except Exception as e:
        print("ERROR OBTENIENDO VIDEO YOUTUBE:", str(e))
        return "Error obteniendo video de YouTube", 500


@app.route("/debug/youtube")
def debug_youtube():
    return jsonify(obtener_videos_youtube())


@app.route("/debug/resolve/<video_id>")
def debug_resolve(video_id):
    try:
        result = obtener_stream_youtube(f"https://www.youtube.com/watch?v={video_id}", cache_key=video_id, live=False)
        return jsonify({
            "title": result["title"],
            "url_preview": result["url"][:120] + "...",
            "streamformat": result.get("streamformat"),
            "format_id": result.get("format_id"),
            "ext": result.get("ext"),
            "protocol": result.get("protocol")
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/static/logo_hd.png")
def static_logo():
    return send_file("images/logo_hd.png", mimetype="image/png")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
