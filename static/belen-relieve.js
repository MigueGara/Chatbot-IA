const ARCHIVO_ATLAS = "belen-prototipo-poses.png";
const ARCHIVO_CUERPO = "belen-prototipo-cuerpo.png";

const limitar = (n, minimo, maximo) => Math.min(maximo, Math.max(minimo, n));
const interpolar = (a, b, peso) => a + (b - a) * peso;

function poseActiva({gesto, escucha}) {
  if (escucha) return 1;
  if (gesto === "pensando") return 2;
  if (gesto === "saludo" || gesto === "lista") return 0;
  return 3;
}

function analizarImagen(imagen, cuerpoCompleto) {
  const ancho = imagen.naturalWidth || imagen.width;
  const alto = imagen.naturalHeight || imagen.height;
  const divisiones = cuerpoCompleto ? 1 : 2;
  const escala = Math.min(1, 640 / Math.max(ancho, alto));
  const muestra = document.createElement("canvas");
  muestra.width = Math.round(ancho * escala);
  muestra.height = Math.round(alto * escala);
  const contexto = muestra.getContext("2d", {willReadFrequently: true});
  contexto.drawImage(imagen, 0, 0, muestra.width, muestra.height);
  const pixeles = contexto.getImageData(0, 0, muestra.width, muestra.height).data;

  const regiones = Array.from({length: divisiones ** 2}, (_, indice) => {
    const columna = indice % divisiones;
    const fila = Math.floor(indice / divisiones);
    const izquierda = Math.floor(muestra.width * columna / divisiones);
    const arriba = Math.floor(muestra.height * fila / divisiones);
    const derecha = Math.floor(muestra.width * (columna + 1) / divisiones);
    const abajo = Math.floor(muestra.height * (fila + 1) / divisiones);
    let x0 = derecha;
    let y0 = abajo;
    let x1 = izquierda;
    let y1 = arriba;
    for (let y = arriba; y < abajo; y++) {
      for (let x = izquierda; x < derecha; x++) {
        if (pixeles[(y * muestra.width + x) * 4 + 3] < 36) continue;
        x0 = Math.min(x0, x);
        y0 = Math.min(y0, y);
        x1 = Math.max(x1, x + 1);
        y1 = Math.max(y1, y + 1);
      }
    }
    if (x0 >= x1 || y0 >= y1) [x0, y0, x1, y1] = [izquierda, arriba, derecha, abajo];

    const altura = y1 - y0;
    const margen = Math.max(2, Math.round(altura * .026));
    const cabeza = centroCabeza(pixeles, muestra.width, x0, y0, x1, altura, cuerpoCompleto);
    return {
      izquierda: Math.max(izquierda, x0 - margen),
      arriba: Math.max(arriba, y0 - margen),
      derecha: Math.min(derecha, x1 + margen),
      abajo: Math.min(abajo, y1 + margen),
      coronilla: y0,
      altura,
      cabeza,
    };
  });
  return {regiones, ancho: muestra.width, alto: muestra.height};
}

function centroCabeza(pixeles, anchoImagen, x0, y0, x1, altura, cuerpoCompleto) {
  const inicio = y0 + Math.floor(altura * (cuerpoCompleto ? .04 : .10));
  const fin = y0 + Math.ceil(altura * (cuerpoCompleto ? .105 : .24));
  let suma = 0;
  let total = 0;
  for (let y = inicio; y < fin; y++) {
    for (let x = x0; x < x1; x++) {
      const alfa = pixeles[(y * anchoImagen + x) * 4 + 3];
      if (alfa < 150) continue;
      suma += x;
      total++;
    }
  }
  return total ? suma / total : (x0 + x1) / 2;
}

function construirPose(THREE, atlas, region, dimensiones, unidad, cuerpoCompleto) {
  const ancho = region.derecha - region.izquierda;
  const alto = region.abajo - region.arriba;
  const textura = atlas.clone();
  textura.colorSpace = THREE.SRGBColorSpace;
  textura.repeat.set(ancho / dimensiones.ancho, alto / dimensiones.alto);
  textura.offset.set(region.izquierda / dimensiones.ancho, 1 - region.abajo / dimensiones.alto);
  textura.needsUpdate = true;

  const geometria = new THREE.PlaneGeometry(ancho * unidad, alto * unidad, 40, 56);
  const vertices = geometria.attributes.position;
  const uv = geometria.attributes.uv;
  const base = new Float32Array(vertices.array.length);
  const boca = new Float32Array(vertices.count);
  const diametroCabeza = region.altura * (cuerpoCompleto ? .14 : .32);
  const centroY = region.coronilla + region.altura * (cuerpoCompleto ? .12 : .30);
  const bocaY = region.coronilla + region.altura * (cuerpoCompleto ? .158 : .385);
  for (let i = 0; i < vertices.count; i++) {
    const x = region.izquierda + uv.getX(i) * ancho;
    const y = region.arriba + (1 - uv.getY(i)) * alto;
    const frente = Math.exp(-(
      ((x - region.cabeza) / (diametroCabeza * .82)) ** 2
      + ((y - centroY) / (diametroCabeza * .95)) ** 2
    ));
    const torso = Math.exp(-(
      ((x - region.cabeza) / (region.altura * .27)) ** 2
      + ((y - region.coronilla - region.altura * .64) / (region.altura * .35)) ** 2
    ));
    vertices.setZ(i, frente * (cuerpoCompleto ? .11 : .21) + torso * .055);
    boca[i] = Math.exp(-(
      ((x - region.cabeza) / (diametroCabeza * .27)) ** 2
      + ((y - bocaY) / (diametroCabeza * .16)) ** 2
    )) * Math.tanh((y - bocaY) / Math.max(1, diametroCabeza * .09));
  }
  base.set(vertices.array);
  const material = new THREE.MeshBasicMaterial({
    map: textura,
    transparent: true,
    alphaTest: .012,
    depthWrite: false,
    toneMapped: false,
  });
  const malla = new THREE.Mesh(geometria, material);
  malla.position.set(
    (region.izquierda + ancho / 2 - region.cabeza) * unidad,
    .97 - (region.arriba + alto / 2 - region.coronilla) * unidad,
    0,
  );
  return {malla, textura, material, geometria, base, boca, apertura: 0};
}

function ajustarBoca(pose, intensidad) {
  if (Math.abs(pose.apertura - intensidad) < .001) return;
  pose.apertura = intensidad;
  const vertices = pose.geometria.attributes.position;
  for (let i = 0; i < vertices.count; i++) {
    if (Math.abs(pose.boca[i]) < .015) continue;
    vertices.setY(i, pose.base[i * 3 + 1] - intensidad * pose.boca[i]);
  }
  vertices.needsUpdate = true;
}

export function montarRelieve(THREE, canvas, contenedor, leerEstado) {
  let terminado = false;
  let renderizador;
  let fotograma = 0;
  let atlas;
  const poses = [];
  const observadores = [];
  const eventos = new AbortController();
  const modo = leerEstado().modo;
  const cuerpoCompleto = modo === "portada";
  const mini = modo === "mini";
  const url = new URL(cuerpoCompleto ? ARCHIVO_CUERPO : ARCHIVO_ATLAS, import.meta.url);
  const escuchaReducida = matchMedia("(prefers-reduced-motion: reduce)");

  function limpiar() {
    terminado = true;
    eventos.abort();
    cancelAnimationFrame(fotograma);
    observadores.forEach(observador => observador.disconnect());
    poses.forEach(({textura, material, geometria}) => {
      textura.dispose();
      material.dispose();
      geometria.dispose();
    });
    atlas?.dispose();
    renderizador?.dispose();
  }

  function iniciar(textura) {
    if (terminado) {
      textura.dispose();
      return;
    }
    atlas = textura;
    try {
      renderizador = new THREE.WebGLRenderer({
        canvas, alpha: true, antialias: true, powerPreference: "low-power",
      });
      renderizador.setPixelRatio(Math.min(window.devicePixelRatio || 1, mini ? 1.35 : 1.65));
      renderizador.setClearColor(0x000000, 0);
      renderizador.outputColorSpace = THREE.SRGBColorSpace;
      const escena = new THREE.Scene();
      const camara = new THREE.OrthographicCamera(-1, 1, 1, -1, .1, 20);
      camara.position.z = 6;
      const personaje = new THREE.Group();
      escena.add(personaje);

      const dimensiones = analizarImagen(atlas.image, cuerpoCompleto);
      const unidad = 1.94 / Math.max(...dimensiones.regiones.map(region => region.altura));
      const estadoInicial = cuerpoCompleto ? 0 : poseActiva(leerEstado());
      dimensiones.regiones.forEach((region, indice) => {
        const pose = construirPose(THREE, atlas, region, dimensiones, unidad, cuerpoCompleto);
        pose.material.opacity = indice === estadoInicial ? 1 : 0;
        pose.malla.visible = pose.material.opacity > 0;
        personaje.add(pose.malla);
        poses.push(pose);
      });

      const extremoIzquierdo = Math.min(...poses.map(({malla, geometria}) => malla.position.x - geometria.parameters.width / 2));
      const extremoDerecho = Math.max(...poses.map(({malla, geometria}) => malla.position.x + geometria.parameters.width / 2));
      const anchoFigura = extremoDerecho - extremoIzquierdo;
      const centroFigura = (extremoDerecho + extremoIzquierdo) / 2;
      let enVista = true;
      let contextoPerdido = false;
      let ultimoCuadro = 0;
      let opacidadLista = estadoInicial;
      let necesitaCuadro = true;
      const mirada = {x: 0, y: 0};
      const inicio = performance.now();

      function encuadrar() {
        const ancho = contenedor.clientWidth;
        const alto = contenedor.clientHeight;
        if (!ancho || !alto || contextoPerdido) return;
        const aspecto = ancho / alto;
        const mitadAlto = Math.max(cuerpoCompleto ? 1.055 : 1.045, (anchoFigura * .52) / aspecto);
        camara.left = centroFigura - mitadAlto * aspecto;
        camara.right = centroFigura + mitadAlto * aspecto;
        camara.top = mitadAlto;
        camara.bottom = -mitadAlto;
        camara.updateProjectionMatrix();
        renderizador.setSize(ancho, alto, false);
        necesitaCuadro = true;
      }

      const medidas = new ResizeObserver(encuadrar);
      const visibilidad = new IntersectionObserver(([entrada]) => { enVista = entrada.isIntersecting; });
      medidas.observe(contenedor);
      visibilidad.observe(contenedor);
      observadores.push(medidas, visibilidad);
      const opciones = {signal: eventos.signal};
      contenedor.addEventListener("pointermove", evento => {
        const limites = contenedor.getBoundingClientRect();
        mirada.x = (evento.clientX - limites.left) / limites.width - .5;
        mirada.y = (evento.clientY - limites.top) / limites.height - .5;
      }, opciones);
      contenedor.addEventListener("pointerleave", () => { mirada.x = mirada.y = 0; }, opciones);
      canvas.addEventListener("webglcontextlost", evento => {
        evento.preventDefault();
        contextoPerdido = true;
        contenedor.dataset.webgl = "respaldo";
      }, opciones);
      canvas.addEventListener("webglcontextrestored", () => {
        contextoPerdido = false;
        encuadrar();
        contenedor.dataset.webgl = "listo";
      }, opciones);

      function dibujar(ahora) {
        if (terminado) return;
        fotograma = requestAnimationFrame(dibujar);
        if (!enVista || contextoPerdido || ahora - ultimoCuadro < (mini ? 64 : 33)) return;
        const estado = leerEstado();
        const indice = cuerpoCompleto ? 0 : poseActiva(estado);
        const sinMovimiento = escuchaReducida.matches;
        if (sinMovimiento && !necesitaCuadro && indice === opacidadLista) return;
        ultimoCuadro = ahora;
        necesitaCuadro = false;
        opacidadLista = indice;
        const tiempo = (ahora - inicio) / 1000;
        const piensa = estado.gesto === "pensando";
        const conversando = estado.escucha || estado.hablando;
        const movimiento = sinMovimiento ? 0 : 1;
        personaje.rotation.y = interpolar(personaje.rotation.y,
          (mirada.x * .17 + Math.sin(tiempo * 1.3) * .038 + (piensa ? -.035 : 0)) * movimiento, .16);
        personaje.rotation.x = interpolar(personaje.rotation.x, (-mirada.y * .10 + (estado.escucha ? .022 : 0)) * movimiento, .16);
        personaje.rotation.z = (Math.sin(tiempo * 1.6) * .008 + (piensa ? -.016 : 0)) * movimiento;
        personaje.position.y = Math.sin(tiempo * (conversando ? 2.65 : 1.75)) * .012 * movimiento;
        const acento = Number.isFinite(estado.acento) ? Math.max(0, .14 - (ahora / 1000 - estado.acento)) * .21 : 0;
        const apertura = estado.hablando && !sinMovimiento
          ? (.012 + Math.abs(Math.sin(tiempo * 13) * Math.sin(tiempo * 4.7)) * .03 + acento) * (cuerpoCompleto ? .45 : 1)
          : 0;
        poses.forEach((pose, posicion) => {
          const meta = posicion === indice ? 1 : 0;
          pose.material.opacity = sinMovimiento ? meta : interpolar(pose.material.opacity, meta, .24);
          pose.malla.visible = pose.material.opacity > .012;
          pose.malla.renderOrder = posicion === indice ? 1 : 0;
          if (pose.malla.visible) ajustarBoca(pose, posicion === indice ? apertura : 0);
        });
        renderizador.render(escena, camara);
      }

      encuadrar();
      renderizador.render(escena, camara);
      contenedor.dataset.webgl = "listo";
      fotograma = requestAnimationFrame(dibujar);
    } catch {
      contenedor.dataset.webgl = "respaldo";
      limpiar();
    }
  }

  new THREE.TextureLoader().load(url.href, iniciar, undefined, () => {
    if (!terminado) contenedor.dataset.webgl = "respaldo";
  });
  return limpiar;
}
