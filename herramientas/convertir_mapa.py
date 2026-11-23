#!/usr/bin/env python3
"""Convierte el mapa de San Aurelio (SVG atlas + mapa de alturas) en datos para el juego.

Uso:  python3 herramientas/convertir_mapa.py
Lee:  herramientas/mapa/atlas_sin_textos.svg, herramientas/mapa/alturas.webp, herramientas/mapa/nombres.json
Deja: herramientas/mapa/datos.json  (lo usa el visor y, en las etapas siguientes, se pega en index.html)

Requiere: numpy, pillow, shapely (pip install shapely).

Unidades: el SVG mide 4000 x 4000. En el juego 1 unidad = ESCALA metros, y el origen (0,0) es el centro
del Parque Centenario. x del SVG -> x del juego; y del SVG (hacia abajo = sur) -> z del juego.
"""
import base64, io, json, math, os, re, sys
from collections import defaultdict

import numpy as np
from PIL import Image
from shapely.geometry import LineString, MultiLineString, Point, Polygon
from shapely.ops import polygonize, unary_union, nearest_points, substring
from shapely.strtree import STRtree

AQUI = os.path.dirname(os.path.abspath(__file__))
MAPA = os.path.join(AQUI, 'mapa')
ESCALA = 0.55
ORIGEN = (2090.0, 2700.0)

# clases de camino (se guardan como número)
CALLE, AVENIDA, BULEVAR, RURAL, AUTOPISTA, RULO, VIA = range(7)
NOMBRE_CLASE = ['calle', 'avenida', 'bulevar', 'rural', 'autopista', 'rulo', 'via']


def M(x, y):
    return [round((x - ORIGEN[0]) * ESCALA, 1), round((y - ORIGEN[1]) * ESCALA, 1)]


def puntos(d):
    return [tuple(map(float, p.split(','))) for p in re.findall(r'[-\d.]+,[-\d.]+', d)]


def grupo(svg, abre):
    """paths dentro del <g ...> cuyo tag de apertura contiene `abre`"""
    i = svg.index(abre)
    i = svg.rfind('<g', 0, i + 1) if not abre.startswith('<g') else i
    j = svg.index('</g>', i)
    return [puntos(d) for d in re.findall(r'd="([^"]*)"', svg[i:j])]


def sueltos(svg, attrs):
    """paths fuera de grupos con estos atributos exactos (sin contar d=)"""
    out = []
    for m in re.finditer(r'<path d="([^"]*)"([^>]*)/>', svg):
        if m.group(2).strip() == attrs:
            out.append(puntos(m.group(1)))
    return out


def con_fill(svg, color):
    return [puntos(d) for d in re.findall(r'<path d="([^"]*)" fill="%s"' % re.escape(color), svg)]


def scale_geom(g, k):
    from shapely import affinity
    return affinity.scale(g, xfact=k, yfact=k, origin=(0, 0))


def main():
    raw = open(os.path.join(MAPA, 'atlas_sin_textos.svg')).read()
    fondo_b64 = re.search(r'href="data:image/png;base64,([^"]*)"', raw).group(1)
    svg = re.sub(r'href="data:[^"]*"', 'href=""', raw)

    # ---------------- caminos ----------------
    capas = [
        (CALLE, grupo(svg, '<g fill="none" stroke="#fbfaf7"')),
        (AVENIDA, grupo(svg, '<g fill="none" stroke="#ffffff" stroke-width="12"')),
        (RURAL, grupo(svg, '<g fill="none" stroke="#f3e9c9"')),
        (BULEVAR, sueltos(svg, 'fill="none" stroke="#ffffff" stroke-width="42"')),
    ]
    autopistas = grupo(svg, '<g fill="none" stroke="#f6b938"')
    rulos = grupo(svg, '<g fill="none" stroke="#f6c75d"')
    vias = sueltos(svg, 'fill="none" stroke="#5b4a3c" stroke-width="5"')

    # Calles a nivel. En el dibujo hay avenidas que corren casi pegadas a una calle, y calles de barrios
    # distintos que se superponen en las costuras. En el juego cada calle mide 20 m de ancho, así que:
    #  1) se aceptan las líneas por prioridad (bulevar, avenidas, rutas, calles; las largas primero);
    #  2) a cada línea nueva se le borra lo que cae a menos de SEP de lo ya aceptado (lo que la duplica);
    #  3) los pedazos que quedan se prolongan en su propia dirección hasta tocar la red (o, si no, al punto
    #     más cercano), así los cruces que el paso 2 cortó vuelven a quedar unidos en el mismo punto.
    SEP, ALCANCE, MIN_PEDAZO = 34.0, 40.0, 18.0
    candidatas = []
    for cl, ps in capas:
        for p in ps:
            ln = LineString(p)
            if len(p) >= 2 and ln.length > 0.5:
                candidatas.append((cl, ln))
    prioridad = {BULEVAR: 0, AVENIDA: 1, RURAL: 2, CALLE: 3}
    candidatas.sort(key=lambda t: (prioridad[t[0]], -t[1].length))
    lineas, clase_de = [], []

    def cerca_de(geom, r, excluir=None):
        if not lineas:
            return []
        arbol = STRtree(lineas)
        return [lineas[j] for j in arbol.query(geom.buffer(r)) if j != excluir]

    def prolongar(pedazo, extremo_inicio, alcance=ALCANCE, excluir=None):
        cs = list(pedazo.coords)
        punta = Point(cs[0] if extremo_inicio else cs[-1])
        if any(ln.distance(punta) < 0.5 for ln in cerca_de(punta, 0.5, excluir)):
            return pedazo   # ya toca otra calle
        if extremo_inicio:
            a, b = cs[0], cs[1]
        else:
            a, b = cs[-1], cs[-2]
        dx, dy = a[0] - b[0], a[1] - b[1]
        n = math.hypot(dx, dy) or 1
        rayo = LineString([a, (a[0] + dx / n * alcance, a[1] + dy / n * alcance)])
        mejor, md = None, 1e9
        for ln in cerca_de(rayo, 1, excluir):
            x = rayo.intersection(ln)
            if x.is_empty:
                continue
            for g in (x.geoms if hasattr(x, 'geoms') else [x]):
                p = g if g.geom_type == 'Point' else Point(g.coords[0])
                d = p.distance(Point(a))
                if 0.05 < d < md:
                    md, mejor = d, p
        if mejor is None:   # sin cruce en línea recta: al punto más cercano, si está cerca
            pa = Point(a)
            lim = min(alcance, SEP + 6)
            for ln in cerca_de(pa, lim, excluir):
                d = ln.distance(pa)
                if 0.05 < d < min(md, lim):
                    md, mejor = d, nearest_points(ln, pa)[0]
        if mejor is None:
            return pedazo
        # se pasa 1 unidad de largo para que el cruce sea real (si cae justo encima, el redondeo
        # puede dejarlo a milímetros sin tocar); la colita que sobra se borra después
        mx, my = mejor.coords[0]
        ux, uy = mx - a[0], my - a[1]
        un = math.hypot(ux, uy) or 1
        fin = (mx + ux / un, my + uy / un)
        nuevo = [fin] + cs if extremo_inicio else cs + [fin]
        return LineString(nuevo)

    def direccion(ln, d):
        a = ln.interpolate(max(0, d - 2)); b = ln.interpolate(min(ln.length, d + 2))
        return math.atan2(b.y - a.y, b.x - a.x)

    def duplica(pt, ang, vecinas):
        """¿el punto está pegado a una calle aceptada que va casi en la misma dirección?"""
        for v in vecinas:
            if v.distance(pt) >= SEP:
                continue
            dv = direccion(v, v.project(pt))
            dif = abs((ang - dv + math.pi / 2) % math.pi - math.pi / 2)
            if dif < math.radians(28):
                return True
        return False

    for cl, ln in candidatas:
        vecinas = cerca_de(ln, SEP)
        PASO = 3.0
        n = max(2, int(ln.length / PASO) + 1)
        marcas = []
        for k in range(n):
            d = ln.length * k / (n - 1)
            marcas.append((d, duplica(ln.interpolate(d), direccion(ln, d), vecinas) if vecinas else False))
        pedazos, ini = [], None
        for d, dup in marcas + [(ln.length, True)]:
            if not dup and ini is None:
                ini = d
            elif dup and ini is not None:
                fin = d if d < ln.length else ln.length
                if fin - ini > 0.5:
                    pedazos.append(substring(ln, ini, fin))
                ini = None
        if ini is not None and ln.length - ini > 0.5:
            pedazos.append(substring(ln, ini, ln.length))
        nuevos = []
        for pz in pedazos:
            if pz.length < MIN_PEDAZO:
                continue
            fue_cortado_ini = Point(pz.coords[0]).distance(Point(ln.coords[0])) > 0.5
            fue_cortado_fin = Point(pz.coords[-1]).distance(Point(ln.coords[-1])) > 0.5
            # los extremos originales también se estiran un poco (las T del dibujo no siempre llegan)
            pz = prolongar(pz, True, ALCANCE if fue_cortado_ini else 14)
            pz = prolongar(pz, False, ALCANCE if fue_cortado_fin else 14)
            nuevos.append(pz)
        for pz in nuevos:
            lineas.append(pz); clase_de.append(cl)
    # última pasada: extremos sueltos que quedaron cerca de calles aceptadas después
    for k in range(len(lineas)):
        lineas[k] = prolongar(prolongar(lineas[k], True, 24, k), False, 24, k)

    # Empalmes en T exactos: cada punta que queda a menos de 3 unidades de otra calle se clava sobre ella y
    # ese punto se inserta como vértice en la otra (si no, el redondeo deja la T a milímetros sin unir).
    coords = [list(l.coords) for l in lineas]
    for k in range(len(coords)):
        for extremo in (0, -1):
            e = Point(coords[k][extremo])
            mejor, md = None, 3.0
            for j in range(len(coords)):
                if j == k:
                    continue
                L = LineString(coords[j])
                d = L.distance(e)
                if d < md:
                    md, mejor = d, j
            if mejor is None:
                continue
            L = coords[mejor]
            # segmento más cercano
            bi, bq, bd = 0, None, 1e9
            for i in range(len(L) - 1):
                seg = LineString([L[i], L[i + 1]])
                q = nearest_points(seg, e)[0]
                d = q.distance(e)
                if d < bd:
                    bi, bq, bd = i, (q.x, q.y), d
            if math.dist(bq, L[bi]) < 0.3:
                bq = L[bi]
            elif math.dist(bq, L[bi + 1]) < 0.3:
                bq = L[bi + 1]
            else:
                L.insert(bi + 1, bq)
            coords[k][extremo] = bq
    lineas = [LineString(c) for c in coords]

    nodado = unary_union(lineas)          # parte todas las líneas en cada cruce
    tramos = list(nodado.geoms) if hasattr(nodado, 'geoms') else [nodado]
    # clase de cada pedacito = la de la línea original más cercana a su punto medio (la más "importante" si empatan)
    arbol = STRtree(lineas)
    def clase_tramo(t):
        mid = t.interpolate(0.5, normalized=True)
        mejor, md = CALLE, 1e9
        for j in arbol.query(mid.buffer(2)):
            d = lineas[j].distance(mid)
            if d < md - 0.3 or (abs(d - md) <= 0.3 and clase_de[j] > mejor and clase_de[j] != RURAL):
                md, mejor = d, clase_de[j]
        return mejor
    # grafo crudo: cada pedacito entre dos cruces es una arista
    nodos, idx = [], {}
    def nodo(c):
        k = (round(c[0], 2), round(c[1], 2))
        if k not in idx:
            idx[k] = len(nodos); nodos.append(k)
        return idx[k]
    aristas = []
    for t in tramos:
        if t.length < 0.05:
            continue
        cs = list(t.coords)
        aristas.append({'a': nodo(cs[0]), 'b': nodo(cs[-1]), 'c': clase_tramo(t), 'p': cs})
    largo = lambda e: LineString(e['p']).length

    def sacar_colitas(aristas, lim):
        for _ in range(4):
            grado = defaultdict(int)
            for e in aristas:
                grado[e['a']] += 1; grado[e['b']] += 1
            aristas = [e for e in aristas if not (largo(e) < lim and (grado[e['a']] == 1 or grado[e['b']] == 1))]
        return aristas
    aristas = sacar_colitas(aristas, 30)

    # Cruces muy cercanos entre sí (restos de empalmes, costuras entre barrios) se funden en uno:
    # en el juego una esquina ocupa unos 20 x 20 m y dos esquinas pegadas se pisarían.
    CONTRAER = 28.0
    padre = list(range(len(nodos)))
    def raiz(i):
        while padre[i] != i:
            padre[i] = padre[padre[i]]; i = padre[i]
        return i
    for e in aristas:
        if largo(e) < CONTRAER:
            padre[raiz(e['a'])] = raiz(e['b'])
    grupos = defaultdict(list)
    for e in aristas:
        for n in (e['a'], e['b']):
            grupos[raiz(n)].append(n)
    pos = {r_: (sum(nodos[i][0] for i in set(m)) / len(set(m)), sum(nodos[i][1] for i in set(m)) / len(set(m))) for r_, m in grupos.items()}
    limpias = []
    for e in aristas:
        a_, b_ = raiz(e['a']), raiz(e['b'])
        if a_ == b_:
            continue
        p = [pos[a_]] + e['p'][1:-1] + [pos[b_]]
        while len(p) > 2 and math.dist(p[1], p[0]) < CONTRAER * 0.6:
            p.pop(1)
        while len(p) > 2 and math.dist(p[-2], p[-1]) < CONTRAER * 0.6:
            p.pop(-2)
        limpias.append({'a': a_, 'b': b_, 'c': e['c'], 'p': p})
    aristas = sacar_colitas(limpias, 30)

    # unir en un solo tramo las cadenas de la misma clase que pasan por nodos de grado 2
    while True:
        inc = defaultdict(list)
        for k, e in enumerate(aristas):
            inc[e['a']].append(k); inc[e['b']].append(k)
        hecho = False
        borrar = set()
        for n, ks in inc.items():
            if len(ks) != 2 or ks[0] == ks[1] or ks[0] in borrar or ks[1] in borrar:
                continue
            e1, e2 = aristas[ks[0]], aristas[ks[1]]
            if e1['c'] != e2['c']:
                continue
            p1 = e1['p'] if e1['b'] == n else e1['p'][::-1]
            a1 = e1['a'] if e1['b'] == n else e1['b']
            p2 = e2['p'] if e2['a'] == n else e2['p'][::-1]
            b2 = e2['b'] if e2['a'] == n else e2['a']
            if a1 == b2:
                continue    # cerraría un anillo
            aristas[ks[0]] = {'a': a1, 'b': b2, 'c': e1['c'], 'p': p1 + p2[1:]}
            borrar.add(ks[1]); hecho = True
        aristas = [e for k, e in enumerate(aristas) if k not in borrar]
        if not hecho:
            break
    # tramos repetidos entre las mismas dos esquinas
    vistas, limpias = set(), []
    for e in aristas:
        k = (min(e['a'], e['b']), max(e['a'], e['b']), round(largo(e) / 10))
        if k not in vistas:
            vistas.add(k); limpias.append(e)
    aristas = limpias
    for e in aristas:
        e['p'] = list(LineString(e['p']).simplify(0.4).coords)
    usados = sorted({e['a'] for e in aristas} | {e['b'] for e in aristas})
    renum = {o: n for n, o in enumerate(usados)}
    nodos = [pos.get(o, nodos[o]) for o in usados]
    for e in aristas:
        e['a'], e['b'] = renum[e['a']], renum[e['b']]

    # ---------------- manzanas ----------------
    # Cada cara del grafo es una manzana. Lo edificable es la cara menos el ancho de las calles que la
    # rodean (medio ancho en metros: calle 10, avenida 13, bulevar 16, ruta 6). Las que quedan chiquitas
    # (triángulos que dejan las diagonales) se guardan aparte como plazoletas.
    MEDIO = {CALLE: 10, AVENIDA: 13, BULEVAR: 16, RURAL: 6}
    urbana = [Polygon(p) for p in sueltos(svg, 'fill="#e6e2da"')]
    red = unary_union([LineString(e['p']) for e in aristas])
    calzadas = unary_union([LineString(e['p']).buffer(MEDIO[e['c']] / ESCALA, cap_style=1, join_style=1) for e in aristas])
    ASFALTO = {CALLE: 4.5, AVENIDA: 7.5, BULEVAR: 11, RURAL: 3.8}     # medio ancho de la calzada (sin vereda)
    asfalto = unary_union([LineString(e['p']).buffer(ASFALTO[e['c']] / ESCALA, cap_style=1, join_style=1) for e in aristas])
    manzanas, plazoletas = [], []           # cada una: (vereda+lote, lote)
    for poly in polygonize(red):
        if poly.area * ESCALA * ESCALA > 80000:
            continue      # el "afuera" de barrios enteros (campo entre rutas)
        def mayor(geo):
            ps = [g for g in (geo.geoms if hasattr(geo, 'geoms') else [geo]) if g.geom_type == 'Polygon']
            return max(ps, key=lambda q: q.area) if ps else None
        vereda = mayor(poly.difference(asfalto))
        if vereda is None or vereda.area * ESCALA * ESCALA < 40:
            continue
        vereda = Polygon(vereda.exterior).simplify(0.6)
        lote = mayor(poly.difference(calzadas))
        if lote is not None:
            lote = Polygon(lote.exterior).simplify(1.0)
        a = lote.area * ESCALA * ESCALA if lote is not None else 0
        if a >= 250:
            manzanas.append((vereda, lote))
        else:
            plazoletas.append(vereda)

    # ---------------- autopistas, rulos, vías ----------------
    def lista(ps, cl):
        return [{'c': cl, 'p': [M(*q) for q in LineString(p).simplify(0.4).coords]} for p in ps]

    # ---------------- costa y suelo (del fondo del SVG) ----------------
    fondo = Image.open(io.BytesIO(base64.b64decode(fondo_b64))).convert('RGB')
    N = 400                                    # 10 unidades por pixel = 5,5 m
    px = np.asarray(fondo.resize((N, N), Image.BILINEAR)).astype(int)
    r, g, b = px[..., 0], px[..., 1], px[..., 2]
    agua = (b > r + 35) & (b > g + 5)
    arena = (~agua) & (r > 225) & (g > 205) & (r - b > 40)
    def mascara_a_poligono(mask):
        cuad = []
        for yy in range(N):
            fila = mask[yy]; xx = 0
            while xx < N:
                if fila[xx]:
                    x0 = xx
                    while xx < N and fila[xx]:
                        xx += 1
                    cuad.append(Polygon([(x0, yy), (xx, yy), (xx, yy + 1), (x0, yy + 1)]))
                else:
                    xx += 1
        u = unary_union(cuad).buffer(0.6).buffer(-0.6)
        return u
    # el río (pintado en el fondo) une el Lago Azul con el mar: se abre la máscara de agua para cortarlo
    charcos = mascara_a_poligono(agua).buffer(-2.0).buffer(2.0)
    partes_agua = sorted(charcos.geoms if hasattr(charcos, 'geoms') else [charcos], key=lambda q: -q.area)
    mar = partes_agua[0]
    tierra = Polygon([(0, 0), (N, 0), (N, N), (0, N)]).difference(mar)
    isla = max(tierra.geoms if hasattr(tierra, 'geoms') else [tierra], key=lambda q: q.area)
    costa = [M(x * 10, y * 10) for x, y in isla.exterior.simplify(0.7).coords]
    lagos = [[M(x * 10, y * 10) for x, y in c.exterior.simplify(0.7).coords] for c in partes_agua[1:] if c.area > 20]
    pl = mascara_a_poligono(arena)
    playas = [[M(x * 10, y * 10) for x, y in p.exterior.simplify(0.7).coords]
              for p in (pl.geoms if hasattr(pl, 'geoms') else [pl]) if p.area > 30]

    # ---------------- alturas ----------------
    # El mapa de alturas cubre los 4000 x 4000 del SVG. La ciudad (menos Las Lomas), el puerto y el
    # aeropuerto se aplanan a 0 con una transición suave; el resto sube hasta HMAX metros.
    H, HMAX = 128, 110
    alt = np.asarray(Image.open(os.path.join(MAPA, 'alturas.webp')).convert('L').resize((H, H), Image.BILINEAR)).astype(float)
    pistas_svg = [Polygon(p) for p in sueltos(svg, 'fill="#4c4f55"')] + [Polygon(p) for p in con_fill(svg, '#7d8fa8')]
    lomas = [k for k, (v, l) in enumerate(manzanas)]   # se completa más abajo con la zona
    gris = (abs(r - 214) < 14) & (abs(g - 211) < 14) & (abs(b - 204) < 14)    # el cemento del fondo (ciudad, puerto)
    gris_geo = scale_geom(mascara_a_poligono(gris).buffer(-1).buffer(1.5), 10)
    plano = unary_union(urbana + [gris_geo] + [p.buffer(60) for p in pistas_svg] + [Polygon(p) for p in sueltos(svg, 'fill="#b8b8b4"')])
    def mascara(geo, n):
        m = np.zeros((n, n))
        paso = 4000 / n
        for j in range(n):
            for i in range(n):
                if geo.contains(Point((i + 0.5) * paso, (j + 0.5) * paso)):
                    m[j, i] = 1
        return m
    def suavizar(m, veces):
        for _ in range(veces):
            p_ = np.pad(m, 1, mode='edge')
            m = sum(p_[1 + dy:1 + dy + m.shape[0], 1 + dx:1 + dx + m.shape[1]] for dy in (-1, 0, 1) for dx in (-1, 0, 1)) / 9
        return m

    # ---------------- detalles ----------------
    def polys(color):
        return [[M(*q) for q in p] for p in con_fill(svg, color)]
    det = {
        'urbana': [[M(*q) for q in p.exterior.coords] for p in urbana],
        'parques': polys('#9fcd7c') + polys('#8cc06b'),
        'agua': polys('#4f9fd0'),
        'rio': [[M(*q) for q in LineString(p).simplify(1).coords] for p in sueltos(svg, 'fill="none" stroke="#4f9fd0" stroke-width="22" stroke-linecap="round" stroke-linejoin="round"')],
        'pistas': [[M(*q) for q in p] for p in sueltos(svg, 'fill="#4c4f55"')],
        'terminal': polys('#7d8fa8') + polys('#b8b8b4'),
        'torres': polys('#a9b4c2'),
        'edificios': polys('#b9b2a6'),
        'galpones': polys('#a7a9ad'),
        'ladrillo': polys('#a0522d'),
        'casas': polys('#c99b7d'),
        'piletas': polys('#4fc3e8'),
        'estaciones': [[M(*q) for q in p] for p in con_fill(svg, '#8f6f5a')],
        'arboles': [M(float(x), float(y)) for x, y in re.findall(r'<circle cx="([\d.]+)" cy="([\d.]+)" r="[\d.]+"/>', svg)],
    }
    nombres = json.load(open(os.path.join(MAPA, 'nombres.json')))
    for n in nombres:
        n['x'], n['z'] = M(n['x'], n['y']); del n['y']

    # ---------------- barrios y zonas ----------------
    # Cada manzana toma el barrio del cartel más cercano (los carteles del atlas marcan el centro de cada
    # barrio). Cada barrio tiene un tipo de zona del juego, que decide cómo se edifica.
    TIPO = {
        'CABALLERO': 'centro', 'ALMENDRO': 'centro', 'LOS TILOS': 'centro',
        'MICROCENTRO': 'torres', 'PUERTO MADERA': 'paseo',
        'BARRIO NORTE': 'barrio', 'VILLA FLORIDA': 'barrio', 'SAN CAYETANO': 'barrio', 'PARQUE SUR': 'barrio',
        'VISTA MAR': 'casitas', 'VILLA DEL SUR': 'casitas',
        'LA RIBERA': 'industrial', 'ZONA PORTUARIA': 'puerto',
        'LAS LOMAS': 'colina', 'PUEBLO ALTO': 'pueblo',
    }
    carteles = [n for n in json.load(open(os.path.join(MAPA, 'nombres.json'))) if n['t'] in TIPO]
    barrios = [n['t'] for n in carteles]
    def barrio_de(par):
        c = par[1].representative_point()
        madera = [u for u in urbana if u.bounds[0] > 3000]          # la franja de Puerto Madera (2º polígono urbano)
        if madera and madera[0].contains(c):
            return barrios.index('PUERTO MADERA')
        cands = [k for k in range(len(carteles)) if barrios[k] != 'PUERTO MADERA']
        return min(cands, key=lambda k: math.hypot(carteles[k]['x'] - c.x, carteles[k]['y'] - c.y))
    zona_manzana = [barrio_de(p) for p in manzanas]

    # Las Lomas no se aplana (la loma sube de verdad)
    tipos = [TIPO[barrios[z]] for z in zona_manzana]
    lomas_geo = unary_union([manzanas[k][0] for k in range(len(manzanas)) if tipos[k] == 'colina']).convex_hull.buffer(40)
    plano_sin_lomas = plano.difference(lomas_geo)
    mplano = np.maximum(suavizar(mascara(plano_sin_lomas, H), 2), mascara(plano_sin_lomas.buffer(-30), H))
    alturas = np.round(alt * (1 - np.clip(mplano, 0, 1))).astype(int)
    # en la loma, piso mínimo para que no queden pozos raros
    alturas = alturas.flatten().tolist()

    # ---------------- tipo de suelo (grilla de 256 x 256 sobre el SVG) ----------------
    # 0 mar, 1 agua dulce, 2 arena, 3 pasto, 4 ciudad (cemento)
    NS = 256
    px2 = np.asarray(fondo.resize((NS, NS), Image.BILINEAR)).astype(int)
    r2, g2, b2 = px2[..., 0], px2[..., 1], px2[..., 2]
    agua2 = (b2 > r2 + 35) & (b2 > g2 + 5)
    arena2 = (~agua2) & (r2 > 225) & (g2 > 205) & (r2 - b2 > 40)
    suelo = np.full((NS, NS), 3)
    ciudad = mascara(plano_sin_lomas.buffer(-4), NS)
    suelo[ciudad > 0] = 4
    suelo[arena2] = 2
    mar_svg = scale_geom(mar, 10)
    paso = 4000 / NS
    for j in range(NS):
        for i in range(NS):
            if agua2[j, i]:
                suelo[j, i] = 0 if mar_svg.contains(Point((i + 0.5) * paso, (j + 0.5) * paso)) else 1
    plano_rle, prev, cuenta = [], None, 0
    for v in suelo.flatten().tolist():
        if v == prev:
            cuenta += 1
        else:
            if prev is not None:
                plano_rle.append('%d%s' % (cuenta, 'masgc'[prev]))
            prev, cuenta = v, 1
    plano_rle.append('%d%s' % (cuenta, 'masgc'[prev]))

    # plazas: lotes que son casi todo parque en el atlas
    verde = unary_union([Polygon(p) for p in con_fill(svg, '#9fcd7c')] + [Polygon(p) for p in sueltos(svg, 'fill="#8cc06b"')]).buffer(0)
    zonas = []
    for k, (v, l) in enumerate(manzanas):
        z = tipos[k]
        if l.intersection(verde).area > 0.4 * l.area:
            z = 'plaza'
        zonas.append(z)

    datos = {
        'escala': ESCALA, 'origen': ORIGEN, 'clases': NOMBRE_CLASE,
        'nodos': [M(*n) for n in nodos],
        'aristas': [[e['a'], e['b'], e['c'], [v for q in e['p'] for v in M(*q)]] for e in aristas],
        'autopistas': lista(autopistas, AUTOPISTA) + lista(rulos, RULO),
        'vias': lista(vias, VIA),
        'manzanas': [{'v': [v for q in list(ve.exterior.coords)[:-1] for v in M(*q)], 'l': [v for q in list(lo.exterior.coords)[:-1] for v in M(*q)], 'z': zonas[k], 'b': zona_manzana[k]} for k, (ve, lo) in enumerate(manzanas)],
        'barrios': [{'n': b, 'tipo': TIPO[b], 'x': M(carteles[k]['x'], carteles[k]['y'])[0], 'z': M(carteles[k]['x'], carteles[k]['y'])[1]} for k, b in enumerate(barrios)],
        'plazoletas': [[v for q in list(p.exterior.coords)[:-1] for v in M(*q)] for p in plazoletas],
        'costa': costa, 'lagos': lagos, 'playas': playas,
        'alturas': {'n': H, 'max': HMAX, 'v': alturas},
        'suelo': {'n': NS, 'rle': ''.join(plano_rle)},
        'detalles': det, 'nombres': nombres,
    }
    out = os.path.join(MAPA, 'datos.json')
    json.dump(datos, open(out, 'w'), separators=(',', ':'), ensure_ascii=False)
    # copia compacta adentro de index.html (sin los nombres de las clases ni el origen)
    juego = {k: v for k, v in datos.items() if k not in ('origen', 'clases')}
    texto = json.dumps(juego, separators=(',', ':'), ensure_ascii=False)
    html_path = os.path.join(AQUI, '..', 'index.html')
    html = open(html_path, encoding='utf-8').read()
    html, n = re.subn(r'(<script id="mapa-datos" type="application/json">).*?(</script>)', lambda m: m.group(1) + texto + m.group(2), html, flags=re.S)
    if n == 1:
        open(html_path, 'w', encoding='utf-8').write(html)
        print('incrustado en index.html', len(texto) // 1024, 'KB')
    gr = defaultdict(int)
    for e in aristas:
        gr[e['a']] += 1; gr[e['b']] += 1
    largo = defaultdict(float)
    for e in aristas:
        largo[NOMBRE_CLASE[e['c']]] += LineString(e['p']).length * ESCALA
    print('nodos', len(nodos), 'aristas', len(aristas), 'sin salida', sum(1 for v in gr.values() if v == 1))
    print('largo por clase (m)', {k: round(v) for k, v in largo.items()})
    print('manzanas', len(manzanas), 'plazoletas', len(plazoletas), 'costa pts', len(costa), 'lagos', len(lagos), 'playas', len(playas))
    print('archivo', out, os.path.getsize(out) // 1024, 'KB')


if __name__ == '__main__':
    main()
