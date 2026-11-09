// Geometría y articulaciones del avatar. La escena aporta cámara y luces.
export function crearBelen(THREE) {
  const raiz = new THREE.Group();
  const cabeza = new THREE.Group();
  cabeza.position.set(0, 1.79, 0);
  raiz.add(cabeza);

  const material = (color, roughness = .72, metalness = 0) =>
    new THREE.MeshStandardMaterial({ color, roughness, metalness });
  const piel = material(0xc98c68, .69);
  const pielSombra = material(0xaf6e56);
  const oreja = material(0xb4745b);
  const labio = material(0x963f49, .52);
  const labioLuz = material(0xb45657, .49);
  const interiorBoca = material(0x351f29);
  const esmalte = material(0xfff1dc, .5);
  const esclera = material(0xffeadf, .46);
  const iris = material(0x51301d, .43);
  const irisLuz = material(0x8c4d2c, .45);
  const pupila = material(0x18131b, .38);
  const montura = material(0x181924, .31, .12);
  const oro = material(0xf5ca78, .28, .56);
  const chaqueta = material(0x26334c, .78);
  const solapa = material(0x323f58, .75);
  const camiseta = material(0x252633, .84);
  const rojo = material(0xbf3946, .66);
  const cabello = [0x211921, 0x2c2028, 0x35242a].map(color => material(color, .52));
  const brilloOjo = new THREE.MeshBasicMaterial({ color: 0xfff8e7 });
  const esfera = new THREE.SphereGeometry(1, 36, 24);

  function malla(padre, geometria, acabado, x = 0, y = 0, z = 0) {
    const objeto = new THREE.Mesh(geometria, acabado);
    objeto.position.set(x, y, z);
    padre.add(objeto);
    return objeto;
  }

  function elipsoide(padre, acabado, x, y, z, ancho, alto, fondo) {
    const objeto = malla(padre, esfera, acabado, x, y, z);
    objeto.scale.set(ancho, alto, fondo);
    return objeto;
  }

  function grupo(padre, x, y, z) {
    const objeto = new THREE.Group();
    objeto.position.set(x, y, z);
    padre.add(objeto);
    return objeto;
  }

  function linea(padre, puntos, grosor, acabado, cerrada = false) {
    const curva = new THREE.CatmullRomCurve3(
      puntos.map(punto => new THREE.Vector3(...punto)), cerrada, "centripetal",
    );
    const geometria = new THREE.TubeGeometry(curva, Math.max(14, puntos.length * 4), grosor, 8, cerrada);
    return malla(padre, geometria, acabado);
  }

  function superficie(padre, puntos, acabado, profundidad) {
    const silueta = new THREE.Shape(puntos.map(([x, y]) => new THREE.Vector2(x, y)));
    silueta.closePath();
    const geometria = new THREE.ShapeGeometry(silueta);
    const vertices = geometria.attributes.position;
    for (let i = 0; i < vertices.count; i++) {
      vertices.setZ(i, profundidad(vertices.getX(i), vertices.getY(i)));
    }
    geometria.computeVertexNormals();
    return malla(padre, geometria, acabado);
  }

  function rejilla(filas, lados, calcular, invertir = false) {
    const posiciones = [];
    const indices = [];
    for (let fila = 0; fila <= filas; fila++) {
      for (let lado = 0; lado <= lados; lado++) {
        posiciones.push(...calcular(fila / filas, lado / lados));
      }
    }
    for (let fila = 0; fila < filas; fila++) {
      for (let lado = 0; lado < lados; lado++) {
        const a = fila * (lados + 1) + lado;
        const b = a + lados + 1;
        if (invertir) {
          indices.push(a, b, a + 1, a + 1, b, b + 1);
        } else {
          indices.push(a, a + 1, b, a + 1, b + 1, b);
        }
      }
    }
    const geometria = new THREE.BufferGeometry();
    geometria.setAttribute("position", new THREE.Float32BufferAttribute(posiciones, 3));
    geometria.setIndex(indices);
    geometria.computeVertexNormals();
    return geometria;
  }

  const torso = [
    [.19, .41, .19], [.25, .44, .20], [.46, .48, .24], [.69, .56, .265],
    [.91, .62, .255], [1.08, .615, .225], [1.16, .51, .19],
    [1.21, .33, .15], [1.24, .20, .13], [1.245, .03, .04],
  ];
  malla(raiz, rejilla(torso.length - 1, 64, (t, u) => {
    const [y, ancho, fondo] = torso[Math.round(t * (torso.length - 1))];
    const angulo = u * Math.PI * 2;
    return [ancho * Math.sin(angulo), y, fondo * Math.cos(angulo)];
  }), chaqueta);

  elipsoide(raiz, piel, 0, 1.235, .015, .163, .27, .15);
  const delante = (x, y) => .276 - .20 * x * x - Math.max(0, y - .93) * .34;
  superficie(raiz, [
    [-.24, 1.19], [-.13, 1.17], [-.067, 1.125], [0, 1.11], [.067, 1.125], [.13, 1.17],
    [.24, 1.19], [.28, .23], [-.28, .23],
  ], camiseta, delante);
  superficie(raiz, [[-.15, 1.212], [0, 1.225], [.15, 1.212], [.09, 1.16], [0, 1.135], [-.09, 1.16]],
    piel, (x, y) => delante(x, y) + .005);

  for (const lado of [-1, 1]) {
    const borde = [[.205, 1.22], [.375, 1.139], [.272, .97], [.347, .91], [.18, .47]]
      .map(([x, y]) => [lado * x, y]);
    superficie(raiz, [...borde, [lado * .153, .78], [lado * .124, 1.121]], solapa,
      (x, y) => delante(x, y) + .013);
    linea(raiz, borde.map(([x, y]) => [x, y, delante(x, y) + .023]), .012, rojo);
    const bolsillo = [[lado * .35, .54], [lado * .46, .565]];
    linea(raiz, bolsillo.map(([x, y]) => [x, y, delante(x, y) - .024]), .013, solapa);
  }
  elipsoide(raiz, oro, -.27, .96, .264, .022, .022, .010);
  elipsoide(raiz, rojo, -.27, .96, .274, .012, .012, .006);

  const rostro = new THREE.SphereGeometry(1, 64, 48);
  const puntosRostro = rostro.attributes.position;
  for (let i = 0; i < puntosRostro.count; i++) {
    const x = puntosRostro.getX(i);
    const y = puntosRostro.getY(i);
    const z = puntosRostro.getZ(i);
    const mandibula = 1 - .25 * Math.max(0, -y - .2);
    const mejilla = 1 + .035 * Math.exp(-((y + .10) ** 2) / .13);
    const frente = z > 0 ? .04 * z * z * (1 - Math.abs(y)) : 0;
    puntosRostro.setXYZ(i, x * .428 * mandibula * mejilla, y * .557, z * .348 + frente);
  }
  rostro.computeVertexNormals();
  malla(cabeza, rostro, piel);

  for (const lado of [-1, 1]) {
    elipsoide(cabeza, piel, lado * .397, -.048, -.02, .082, .121, .073);
    elipsoide(cabeza, oreja, lado * .437, -.043, .025, .033, .070, .028);
    elipsoide(cabeza, oro, lado * .435, -.132, .035, .029, .038, .024);
  }

  elipsoide(cabeza, piel, 0, -.051, .366, .045, .099, .043);
  elipsoide(cabeza, piel, 0, -.109, .402, .061, .046, .046);
  for (const lado of [-1, 1]) {
    elipsoide(cabeza, piel, lado * .043, -.126, .38, .035, .027, .033);
    elipsoide(cabeza, pielSombra, lado * .034, -.141, .404, .014, .006, .008);
  }

  const ojos = [];
  const cejas = [];
  const miradas = [];
  for (const lado of [-1, 1]) {
    const ojo = grupo(cabeza, lado * .165, .041, .331);
    ojo.rotation.y = lado * .14;
    ojos.push(ojo);
    elipsoide(ojo, esclera, 0, 0, 0, .109, .064, .046);
    const mirada = grupo(ojo, 0, 0, 0);
    miradas.push(mirada);
    elipsoide(mirada, iris, 0, 0, .040, .047, .049, .015);
    elipsoide(mirada, irisLuz, 0, -.008, .050, .036, .037, .011);
    elipsoide(mirada, pupila, 0, .002, .056, .025, .030, .012);
    elipsoide(mirada, brilloOjo, -.014, .019, .066, .012, .011, .004);
    elipsoide(mirada, brilloOjo, .015, -.014, .067, .004, .004, .002);
    linea(ojo, [[-.105, .002, .005], [-.071, .043, .031], [-.019, .061, .034],
      [.041, .056, .033], [.081, .031, .022], [.108, .001, .006]], .011, cabello[0]);
    const ceja = grupo(cabeza, lado * .174, .151, .326);
    cejas.push(ceja);
    linea(ceja, [[lado * -.077, -.008, .013], [lado * -.043, .011, .013],
      [lado * .014, .023, .003], [lado * .056, .013, -.013],
      [lado * .093, -.006, -.025]], .019, cabello[1]);
  }

  const boca = grupo(cabeza, 0, -.229, .337);
  const sonrisa = new THREE.Shape();
  sonrisa.moveTo(-.104, .014);
  sonrisa.bezierCurveTo(-.064, .000, .058, -.001, .103, .015);
  sonrisa.bezierCurveTo(.057, -.041, -.041, -.050, -.104, .014);
  malla(boca, new THREE.ShapeGeometry(sonrisa), interiorBoca, 0, 0, .012);
  linea(boca, [[-.104, .014, .006], [-.049, .008, .015], [-.023, .010, .021],
    [0, .007, .023], [.025, .011, .022], [.055, .009, .016], [.104, .014, .005]], .009, labio);
  linea(boca, [[-.099, .010, .007], [-.054, -.017, .016], [0, -.027, .021],
    [.056, -.016, .017], [.099, .010, .006]], .011, labioLuz);
  const dientes = superficie(boca, [[-.067, .007], [.068, .007], [.050, -.006],
    [.012, -.014], [-.027, -.013], [-.052, -.006]], esmalte, () => .016);

  function lente(lado) {
    const gafas = grupo(cabeza, lado * .168, .038, .410);
    gafas.rotation.y = lado * .18;
    const ancho = .133;
    const alto = .091;
    const radio = .036;
    const silueta = new THREE.Shape();
    silueta.moveTo(-ancho + radio, alto);
    silueta.lineTo(ancho - radio, alto);
    silueta.quadraticCurveTo(ancho, alto, ancho, alto - radio);
    silueta.lineTo(ancho, -alto + radio);
    silueta.quadraticCurveTo(ancho, -alto, ancho - radio, -alto);
    silueta.lineTo(-ancho + radio, -alto);
    silueta.quadraticCurveTo(-ancho, -alto, -ancho, -alto + radio);
    silueta.lineTo(-ancho, alto - radio);
    silueta.quadraticCurveTo(-ancho, alto, -ancho + radio, alto);
    linea(gafas, silueta.getPoints(8).slice(0, -1).map(({ x, y }) => [x, y, 0]), .015, montura, true);
    elipsoide(gafas, oro, lado * .122, .058, .013, .012, .008, .005);
  }
  lente(-1);
  lente(1);
  linea(cabeza, [[-.038, .059, .407], [-.019, .082, .418], [.018, .082, .418], [.039, .059, .407]],
    .012, montura);
  for (const lado of [-1, 1]) {
    linea(cabeza, [[lado * .297, .080, .382], [lado * .342, .072, .320],
      [lado * .401, .041, .122], [lado * .424, -.018, .014]], .015, montura);
  }

  // El caparazón del pelo deja libre la frente y cae hasta la nuca.
  malla(cabeza, rejilla(30, 80, (t, u) => {
    const giro = u * Math.PI * 2;
    const frente = Math.max(0, Math.cos(giro));
    const nuca = Math.max(0, -Math.cos(giro));
    const final = 1.75 - .87 * frente + 1.16 * nuca + .08 * Math.sin(giro);
    const polar = Math.max(.002, t * final);
    return [
      .456 * Math.sin(polar) * Math.sin(giro),
      .600 * Math.cos(polar) + .018,
      .376 * Math.sin(polar) * Math.cos(giro) - .013,
    ];
  }, true), cabello[1]);

  function mechon(puntos, ancho, fondo, tono) {
    const curva = new THREE.CatmullRomCurve3(puntos.map(punto => new THREE.Vector3(...punto)));
    const geometria = rejilla(36, 20, (t, u) => {
      const centro = curva.getPointAt(t);
      const eje = curva.getTangentAt(t);
      const lateral = new THREE.Vector3().crossVectors(eje, new THREE.Vector3(0, 0, 1)).normalize();
      const normal = new THREE.Vector3().crossVectors(lateral, eje).normalize();
      const angulo = u * Math.PI * 2;
      const perfil = Math.max(.026, Math.sin(Math.PI * t) ** .54);
      const relieve = 1 + .045 * Math.cos(angulo * 7 + t * 4) * Math.sin(t * Math.PI);
      centro.addScaledVector(lateral, Math.cos(angulo) * ancho * perfil * relieve);
      centro.addScaledVector(normal, Math.sin(angulo) * fondo * perfil);
      return centro.toArray();
    }, true);
    malla(cabeza, geometria, cabello[tono]);
  }

  for (const lado of [-1, 1]) {
    const reflejar = puntos => puntos.map(([x, y, z]) => [lado * x, y, z]);
    mechon(reflejar([[.15, .563, -.08], [.36, .40, -.18], [.45, .08, -.19], [.43, -.37, -.21],
      [.54, -.72, -.18], [.59, -1.08, -.16], [.47, -1.28, -.10]]), .153, .126, 0);
    mechon(reflejar([[.20, .541, .14], [.385, .322, .04], [.446, .041, .008], [.455, -.24, -.007],
      [.414, -.51, .022], [.53, -.81, .052], [.527, -1.12, .076], [.40, -1.24, .10]]), .101, .100, 1);
    mechon(reflejar([[.31, .395, .12], [.417, .202, .12], [.431, -.18, .092], [.409, -.41, .119],
      [.434, -.69, .171], [.482, -.91, .158], [.409, -1.12, .141]]), .071, .073, lado < 0 ? 2 : 1);
    mechon(reflejar([[.39, .164, .079], [.465, -.13, .066], [.49, -.44, -.015], [.46, -.61, .04],
      [.542, -.82, .09], [.50, -1.046, .072]]), .070, .065, 1);
  }
  mechon([[-.169, .546, .145], [-.054, .545, .204], [.145, .471, .268], [.28, .334, .279],
    [.369, .214, .232], [.431, .168, .156], [.443, .052, .083]], .119, .071, 1);
  mechon([[-.151, .561, .127], [-.022, .575, .147], [.157, .531, .190], [.310, .406, .218],
    [.392, .274, .177], [.419, .132, .151]], .087, .070, 2);
  mechon([[-.177, .556, .146], [-.258, .479, .218], [-.323, .372, .250],
    [-.377, .261, .222], [-.409, .13, .150], [-.429, -.063, .105]], .092, .068, 1);
  mechon([[-.180, .554, .159], [-.246, .522, .202], [-.326, .430, .226],
    [-.384, .304, .201], [-.408, .145, .159]], .052, .053, 2);
  mechon([[-.154, .574, .083], [.014, .602, .020], [.207, .555, -.024],
    [.358, .426, -.057], [.442, .233, -.065]], .092, .070, 1);

  const brazos = [-1, 1].map(lado => {
    const hombro = grupo(raiz, lado * .512, 1.08, -.02);
    elipsoide(hombro, chaqueta, lado * .045, -.152, 0, .151, .273, .171);
    const codo = grupo(hombro, lado * .073, -.360, 0);
    elipsoide(codo, chaqueta, 0, -.14, .008, .119, .224, .134);
    elipsoide(codo, rojo, 0, -.300, .016, .105, .052, .112);
    const mano = grupo(codo, 0, -.315, .016);
    elipsoide(mano, piel, 0, -.078, 0, .073, .097, .042);
    const dedos = [[-.050, .071], [-.019, .091], [.014, .088], [.043, .070]];
    dedos.forEach(([x, largo]) => {
      const dedo = elipsoide(mano, piel, x, -.143, .001, .020, largo, .025);
      dedo.rotation.z = x * 3;
    });
    const pulgar = elipsoide(mano, piel, -lado * .067, -.073, .008, .023, .052, .028);
    pulgar.rotation.z = -lado * .58;
    return { hombro, codo, mano };
  });

  return { raiz, cabeza, ojos, cejas, boca, dientes, brazos, miradas };
}
