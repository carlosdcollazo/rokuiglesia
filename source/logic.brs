sub init()
    ' Componentes principales
    m.menu = m.top.findNode("menuIglesia")
    m.videoList = m.top.findNode("listaVideos")
    m.slide = m.top.findNode("slideShowFotos")
    m.overlayAzul = m.top.findNode("overlayAzul")
    m.overlayDegradado = m.top.findNode("overlayDegradado")
    m.panelVideoList = m.top.findNode("panelListaVideos")
    m.lineaLista = m.top.findNode("lineaLista")
    m.tituloSeccion = m.top.findNode("tituloSeccion")
    m.previewThumb = m.top.findNode("previewThumb")
    m.previewTitle = m.top.findNode("previewTitle")
    m.previewHint = m.top.findNode("previewHint")
    m.mensajeEstado = m.top.findNode("mensajeEstado")
    m.homeHeadline = m.top.findNode("homeHeadline")
    m.homeText = m.top.findNode("homeText")
    m.splashBg = m.top.findNode("splashBg")
    m.splashLogo = m.top.findNode("splashLogo")
    m.splashTitle = m.top.findNode("splashTitle")
    m.timer = m.top.findNode("fotoTimer")
    m.splashTimer = m.top.findNode("splashTimer")

    m.baseUrl = "http://192.168.1.150:5000/feed/"

    m.menu.content = crearMenu()
    m.menu.setFocus(true)

    m.menu.observeField("itemSelected", "alSeleccionarMenu")
    m.videoList.observeField("itemSelected", "alSeleccionarVideo")
    m.videoList.observeField("itemFocused", "actualizarPreviewVideo")
    m.timer.observeField("fire", "cambiarSiguienteFoto")
    m.splashTimer.observeField("fire", "ocultarSplash")

    m.fotoIndex = 0
    m.indiceActualVideo = -1
    cargarFotosDeActividades()
    m.splashTimer.control = "start"
end sub

function crearMenu() as object
    content = CreateObject("roSGNode", "ContentNode")

    opciones = [
        { title: "🔴 EN VIVO", id: "live" },
        { title: "PREDICACIONES", id: "predicaciones" },
        { title: "ESTUDIOS BÍBLICOS", id: "estudios" },
        { title: "PODCAST", id: "podcast" }
    ]

    for each opt in opciones
        item = content.CreateChild("ContentNode")
        item.title = opt.title
        item.id = opt.id
    next

    return content
end function

function tituloDeSeccion(id as string) as string
    if id = "live" then return "Transmisión en Vivo"
    if id = "predicaciones" then return "Predicaciones"
    if id = "estudios" then return "Estudios Bíblicos"
    if id = "podcast" then return "Podcast"
    return "Videos"
end function

sub ocultarSplash()
    m.splashBg.visible = false
    m.splashLogo.visible = false
    m.splashTitle.visible = false
end sub

sub alSeleccionarMenu()
    indice = m.menu.itemSelected
    item = m.menu.content.getChild(indice)

    m.seccionActual = item.id
    mostrarCargando("Cargando " + tituloDeSeccion(m.seccionActual) + "...")

    m.contentReader = CreateObject("roSGNode", "ContentReader")
    m.contentReader.uri = m.baseUrl + item.id
    m.contentReader.observeField("content", "mostrarListaVideos")
    m.contentReader.control = "RUN"
end sub

sub cargarFotosDeActividades()
    m.fotoTask = CreateObject("roSGNode", "ContentReader")
    m.fotoTask.uri = m.baseUrl + "fotos"
    m.fotoTask.observeField("content", "empezarSlideshow")
    m.fotoTask.control = "RUN"
end sub

sub empezarSlideshow()
    if m.fotoTask.content <> invalid
        m.listaFotos = m.fotoTask.content.getChildren(-1, 0)
        if m.listaFotos.count() > 0
            m.fotoIndex = 0
            cambiarSiguienteFoto()
            m.timer.control = "start"
        else
            print "No hay fotos para el slideshow"
        end if
    end if
end sub

sub cambiarSiguienteFoto()
    if m.listaFotos <> invalid and m.listaFotos.count() > 0
        foto = m.listaFotos[m.fotoIndex]
        m.slide.translation = [0, 0]
        m.slide.width = 1280
        m.slide.height = 720
        m.slide.loadDisplayMode = "scaleToFill"
        m.slide.uri = foto.url

        m.fotoIndex++
        if m.fotoIndex >= m.listaFotos.count() then m.fotoIndex = 0
    end if
end sub

sub mostrarCargando(texto as string)
    m.mensajeEstado.text = texto
    m.mensajeEstado.visible = true
    m.videoList.visible = false
    m.panelVideoList.visible = false
    m.lineaLista.visible = false
    m.tituloSeccion.visible = false
    m.previewThumb.visible = false
    m.previewTitle.visible = false
    m.previewHint.visible = false
end sub

sub mostrarHome()
    m.menu.visible = true
    m.homeHeadline.visible = true
    m.homeText.visible = true
    m.videoList.visible = false
    m.panelVideoList.visible = false
    m.lineaLista.visible = false
    m.tituloSeccion.visible = false
    m.previewThumb.visible = false
    m.previewTitle.visible = false
    m.previewHint.visible = false
    m.mensajeEstado.visible = false
    m.menu.setFocus(true)
end sub

sub mostrarListaVideos()
    m.mensajeEstado.visible = false

    if m.contentReader.content <> invalid
        m.listaDeVideos = m.contentReader.content

        if m.listaDeVideos.getChildCount() > 0
            print "Videos encontrados: "; m.listaDeVideos.getChildCount()

            if m.seccionActual = "live" and m.listaDeVideos.getChildCount() = 1
                video = m.listaDeVideos.getChild(0)
                configurarReproductor(video)
            else
                m.videoList.content = m.listaDeVideos
                m.videoList.visible = true
                m.panelVideoList.visible = true
                m.lineaLista.visible = true
                m.tituloSeccion.text = tituloDeSeccion(m.seccionActual)
                m.tituloSeccion.visible = true
                m.previewThumb.visible = true
                m.previewTitle.visible = true
                m.previewHint.visible = true
                m.menu.visible = false
                m.homeHeadline.visible = false
                m.homeText.visible = false
                m.slide.visible = true
                m.overlayAzul.visible = true
                m.overlayDegradado.visible = true
                m.videoList.setFocus(true)
                m.indiceActualVideo = 0
                actualizarPreviewVideo()
            end if
        else
            if m.seccionActual = "live"
                m.mensajeEstado.text = "No hay transmisión en vivo actualmente.\nVuelva a intentar cuando comience el culto."
            else
                m.mensajeEstado.text = "No se encontraron videos para esta sección."
            end if
            m.mensajeEstado.visible = true
            m.menu.visible = true
            m.homeHeadline.visible = false
            m.homeText.visible = false
            m.menu.setFocus(true)
        end if
    else
        m.mensajeEstado.text = "No llegó contenido para esta sección."
        m.mensajeEstado.visible = true
    end if
end sub

sub actualizarPreviewVideo()
    if m.listaDeVideos <> invalid and m.videoList.visible = true
        index = m.videoList.itemFocused
        if index < 0 then index = 0
        if index < m.listaDeVideos.getChildCount()
            m.indiceActualVideo = index
            video = m.listaDeVideos.getChild(index)
            m.previewTitle.text = video.title
            if video.hdPosterUrl <> invalid and video.hdPosterUrl <> ""
                m.previewThumb.uri = video.hdPosterUrl
            else if video.sdPosterUrl <> invalid and video.sdPosterUrl <> ""
                m.previewThumb.uri = video.sdPosterUrl
            else
                m.previewThumb.uri = "pkg:/images/logo_hd.png"
            end if
        end if
    end if
end sub

sub alSeleccionarVideo()
    if m.listaDeVideos <> invalid and m.videoList.itemSelected >= 0
        index = m.videoList.itemSelected
        video = m.listaDeVideos.getChild(index)
        configurarReproductor(video)
    end if
end sub

sub configurarReproductor(video)
    print "VIDEO SELECCIONADO: "; video.title
    print "URL RECIBIDA: "; video.url
    print "FORMATO RECIBIDO: "; video.streamFormat

    if video.streamFormat = "resolver"
        m.videoPendienteTitulo = video.title
        mostrarCargando("Preparando transmisión...")
        m.streamResolver = CreateObject("roSGNode", "StreamResolver")
        m.streamResolver.uri = video.url
        m.streamResolver.title = video.title
        m.streamResolver.observeField("content", "alResolverStream")
        m.streamResolver.observeField("error", "alErrorResolverStream")
        m.streamResolver.control = "RUN"
        return
    end if

    reproducirVideoDirecto(video)
end sub

sub alResolverStream()
    if m.streamResolver <> invalid and m.streamResolver.content <> invalid
        print "STREAM RESUELTO: "; m.streamResolver.content.url
        reproducirVideoDirecto(m.streamResolver.content)
    else
        m.mensajeEstado.text = "No se pudo preparar el video."
        m.mensajeEstado.visible = true
    end if
end sub

sub alErrorResolverStream()
    if m.streamResolver <> invalid
        print "ERROR RESOLVIENDO STREAM: "; m.streamResolver.error
        m.mensajeEstado.text = m.streamResolver.error
        m.mensajeEstado.visible = true
    end if
end sub

sub reproducirVideoDirecto(video)
    m.videoPlayer = m.top.findNode("videoPlayerActivo")

    if m.videoPlayer = invalid
        m.videoPlayer = CreateObject("roSGNode", "Video")
        m.videoPlayer.id = "videoPlayerActivo"
        m.top.appendChild(m.videoPlayer)
        m.videoPlayer.observeField("state", "verificarEstadoVideo")
    end if

    print "REPRODUCIENDO TITULO: "; video.title
    print "REPRODUCIENDO URL FINAL: "; video.url
    print "STREAM FORMAT FINAL: "; video.streamFormat

    m.videoPlayer.translation = [0, 0]
    m.videoPlayer.width = 1280
    m.videoPlayer.height = 720
    m.videoPlayer.loadDisplayMode = "scaleToFit"

    m.videoList.visible = false
    m.panelVideoList.visible = false
    m.lineaLista.visible = false
    m.tituloSeccion.visible = false
    m.previewThumb.visible = false
    m.previewTitle.visible = false
    m.previewHint.visible = false
    m.menu.visible = false
    m.homeHeadline.visible = false
    m.homeText.visible = false
    m.slide.visible = false
    m.overlayAzul.visible = false
    m.overlayDegradado.visible = false
    m.mensajeEstado.visible = false

    m.videoPlayer.content = video
    m.videoPlayer.visible = true
    m.videoPlayer.setFocus(true)
    m.videoPlayer.control = "play"
end sub

sub verificarEstadoVideo()
    if m.videoPlayer <> invalid
        print "ESTADO VIDEO: "; m.videoPlayer.state
        print "ERROR CODE: "; m.videoPlayer.errorCode
        print "ERROR MSG: "; m.videoPlayer.errorMsg

        if m.videoPlayer.state = "finished"
            reproducirSiguienteSiExiste()
        else if m.videoPlayer.state = "error"
            cerrarReproductor()
            m.mensajeEstado.text = "No se pudo reproducir este video. Intente otro."
            m.mensajeEstado.visible = true
        end if
    end if
end sub

sub reproducirSiguienteSiExiste()
    if m.listaDeVideos <> invalid and m.videoList <> invalid and m.seccionActual <> "live"
        proximo = m.videoList.itemSelected + 1
        if proximo >= 0 and proximo < m.listaDeVideos.getChildCount()
            video = m.listaDeVideos.getChild(proximo)
            m.videoList.jumpToItem = proximo
            configurarReproductor(video)
            return
        end if
    end if
    cerrarReproductor()
end sub

sub cerrarReproductor()
    if m.videoPlayer <> invalid
        m.videoPlayer.control = "stop"
        m.videoPlayer.visible = false
        m.top.removeChild(m.videoPlayer)
        m.videoPlayer = invalid
    end if

    m.slide.visible = true
    m.overlayAzul.visible = true
    m.overlayDegradado.visible = true

    if m.listaDeVideos <> invalid and m.listaDeVideos.getChildCount() > 0 and m.seccionActual <> "live"
        m.videoList.visible = true
        m.panelVideoList.visible = true
        m.lineaLista.visible = true
        m.tituloSeccion.visible = true
        m.previewThumb.visible = true
        m.previewTitle.visible = true
        m.previewHint.visible = true
        m.menu.visible = false
        m.homeHeadline.visible = false
        m.homeText.visible = false
        m.videoList.setFocus(true)
        actualizarPreviewVideo()
    else
        mostrarHome()
    end if
end sub

sub volverAlMenuPrincipal()
    if m.videoPlayer <> invalid and m.videoPlayer.visible = true
        cerrarReproductor()
        return
    end if
    mostrarHome()
end sub

function onKeyEvent(key as String, press as Boolean) as Boolean
    if press then
        if key = "back"
            if m.videoPlayer <> invalid and m.videoPlayer.visible = true
                cerrarReproductor()
                return true
            else if m.videoList <> invalid and m.videoList.visible = true
                volverAlMenuPrincipal()
                return true
            else if m.mensajeEstado <> invalid and m.mensajeEstado.visible = true
                mostrarHome()
                return true
            end if
        end if
    end if
    return false
end function
