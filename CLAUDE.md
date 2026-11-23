# Calle Brava — memoria del proyecto

Juego 3D de calle en el navegador. Todo el juego vive en **un solo archivo: `index.html`**.

- Online: https://jedbweb-ai.github.io/calle-brava/ (GitHub Pages, rama `main`, carpeta raíz; se actualiza solo con cada push)
- Copia vieja en claude.ai: https://claude.ai/artifact/WxgbWgphkHETYPxrqa8x9j — quedó congelada; no actualizarla salvo que la persona lo pida.
- `.nojekyll` existe para que Pages sirva el HTML tal cual.

## Reglas fijas

- Three.js **r128** desde cdnjs (`https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js`). No cambiar de versión.
- **No hay imágenes**: todas las texturas se pintan en `<canvas>` al cargar.
- Todo el texto del juego en **español rioplatense** (voseo: "tocá", "rajá", "apuntá").
- Nada de marcas, logos ni nombres de empresas reales (los bancos son "Banco de Barrio", "Banco del Sur", "Banco del Plata").
- Forma de trabajo pedida: probar en un navegador local antes de publicar y contar qué se probó y qué no.
- Publicar = commit + push a `main`; después confirmar el deploy con la API (`repos/jedbweb-ai/calle-brava/actions/runs`, "pages build and deployment": success), porque github.io no se puede abrir desde la nube.
- Crédito del autor: "Creado por Julián Domenech" con link a https://juliandomenech.com (pestaña nueva), al pie del menú de Pausa/Opciones (`.credit`). No sacarlo.

## Cómo probar localmente

En la nube cdnjs y github.io suelen estar bloqueados. Bajar three r128 con `npm pack three@0.128.0` y, en Playwright,
interceptar `**/three.min.js` con `route.fulfill({ path: .../package/build/three.min.js })`; abortar `fonts.googleapis.com`.
Para manejar el juego desde el test, hacer una **copia** del HTML que agregue antes del cierre `})();` algo como
`window.__g = { player, get state(){return state}, get room(){return room}, bizSpots, enterBiz, ... }`. No commitear esa copia.
El botón `#enter` rebota (animación): clickearlo con `{ force: true }`.

## El mapa: San Aurelio (rama de trabajo `mapa-nuevo`; backup de la ciudad vieja en `backup-mapa-original`)

- **Fuente:** `herramientas/mapa/atlas_sin_textos.svg` (atlas 4000×4000 con calles, manzanas, parques, puerto, aeropuerto), `alturas.webp` (relieve) y `nombres.json` (carteles del atlas).
  `python3 herramientas/convertir_mapa.py` (necesita numpy, pillow, shapely) genera `herramientas/mapa/datos.json` **y lo copia adentro de `index.html`**
  en `<script id="mapa-datos" type="application/json">` (no editar a mano). `herramientas/visor.html` dibuja los datos sobre el atlas para controlarlos (servir el repo con `python3 -m http.server`).
- **Escala:** 1 unidad del SVG = 0,55 m; origen (0,0) = centro del Parque Centenario; x = este, z = sur. Isla de ~2,2 km.
- **Qué hace el conversor:** une calles, avenidas, bulevar y rutas en un **grafo** (cruces = nodos, tramos = aristas). Borra calles paralelas pegadas
  (`SEP_PARALELA`, salvo en el Microcentro), empalma las T y funde esquinas a menos de ~15 m. Saca las **manzanas** como caras del grafo:
  `v` = manzana con vereda, `l` = lote edificable y `r` = rectángulo inscripto girado (para las celdas). Además zona y barrio por manzana (cartel más cercano),
  costa, lagos y dársenas, playas, alturas 128², suelo 256² (mar/agua/arena/pasto/cemento, en RLE), autopistas y rulos aparte, y detalles
  (pistas, terminal, hangares, grúas, contenedores, muelle, árboles…).
- **Anchos (medio ancho calzada / con veredas):** calle 4,5/9 · avenida 6,5/11 · bulevar 11/16 · ruta 3,8/6 · pasaje del Microcentro 3,4/6,5 (`ASF`, `MEDIO`, por clase 0,1,2,3,7).
- **Barrios → zonas del juego:** Caballero, Almendro, Los Tilos = centro · Microcentro = torres · Puerto Madera = paseo · Barrio Norte, Villa Florida, San Cayetano, Parque Sur = barrio ·
  Vista Mar, Villa del Sur = casitas · Pueblo Alto = pueblo · La Ribera = industrial · Zona Portuaria = puerto · Las Lomas = colina. Manzanas que son casi todo parque = plaza.
- **Lugares fijos** (`asignarCeldas`): Banco de Barrio en Almendro, Banco del Sur en Puerto Madera, Banco del Plata en Microcentro; comisarías en Caballero, Microcentro y Villa Florida;
  hospitales en Los Tilos, San Cayetano, Vista Mar, Barrio Norte y Parque Sur; súper en Villa Florida, Caballero, San Cayetano y Barrio Norte; iglesias en Los Tilos y Villa del Sur.
  El resto (más iglesias, escuelas, nafta, armerías, negocios robables, callejones) se sortea con `hash`, igual en cada partida. Los Rojos en San Cayetano, Los Azules en Villa Florida.

## Mapa del código (secciones del `<script>`, en orden)

`P`/`DIRS`/`pushOut` → **mapa** (`MAPA`, `NODOS`, `ARISTAS`, `MANZANAS`, grilla de búsqueda `celdas` de 32 m, `calleAt`, `manzanaAt`, `hgt`, `sueloAt`, `enTierra`, `zoneAt`/`zonaMapa`,
`clampWalk`, `solidAt`, obstáculos sueltos `agregarObs`, `MUELLES`) → **recorridos** (`ptArista`, `elegirSalida`, `rutaDesde`, `adelante`, `avanzarRuta`, `lugarEnRed`, `streetSpot`, `lateralOf`) →
renderer y texturas en canvas → **suelo** (`armarSuelo`: relieve, calzadas, esquinas, rayas, sendas, veredas con cordón, lotes, en baldosas de 256 m) → **autopistas** (`AUTOS`, `deckAt`, `nivelEntidad`, `armarAutopistas`) →
mar → edificios por zona (`buildCentro`, `buildTowers`, `buildSpecial`, `buildBank`…) → **celdas** (`CELDAS`, `asignarCeldas`, `obsDeCelda`, `armarCelda`, `armarManzana`, `updateBlocks`: se arman las manzanas a menos de 115 m) →
armas → personajes (`makePerson`, `randomRig`) → jugador (`INICIO`) → peatones →
autos (`spawnCar`, `CARRIL`, `conducirIA`, `spawnAutoAU`) → efectos/sonido (`sfx`) → combate (`startAttack`, `resolveHit`, `poseAttack`) → HUD/minimapa/mapa grande (`pintarMapa`: la isla entera en un canvas de 2048 px; el minimapa recorta y dibuja encima en vector) → input →
armería → armas de fuego → picadas (`buildRoute`) → bandas (`armarBandas`) → policía (`addHeat`, `calcDistJugador`, `policeDrive`, `updatePolice`, `dispatches`) → helicóptero →
aeropuerto/aviones (`AEROP`, `initAirport`), puerto (`initPort`), playas y muelle (`initPlaya`, `updatePlaya`) → **negocios y robos** (`BIZ`, `bizSpot`, `buildRoom`, `enterBiz`/`leaveBiz`, `startHeist`, `updateRoom*`) →
**trabajos** (`JOB_INFO`, `placeLabel`, `jobSpot`, `updateJob`, ambulancia) → **llamadas** (`startPhone`, `updateMedics`, `policeCalled`, `laneTowards`) → pausa/opciones → estado de juego → `frame()`.

## Cómo está hecho hoy (decisiones ya tomadas)

- **Edificios en celdas:** el rectángulo `r` de cada manzana se parte en celdas de ~28 m; cada celda es un grupo girado y apenas estirado (`sx`, `sz`) donde los constructores de siempre
  dibujan en coordenadas locales 0..28 (`XF` hace que `hgt` funcione en local, para las mansiones de la loma). El frente (z local 28) mira al borde más cercano.
  Lo sólido de cada celda (`ce.obs`) son rectángulos en su marco girado; lo que sobra del lote es explanada caminable. No se construye debajo de las autopistas.
- **Autopistas:** elevadas 7,5 m donde pasan sobre la ciudad, rampas del 10 %, las puntas libres bajan al suelo. Autos y jugador tienen `nivel` (0 suelo, 1 autopista) e `y`;
  `nivelEntidad` los sube, baja o los frena contra las barandas. Cosas en niveles distintos no se chocan. Se entra y se sale por las puntas y donde van a nivel.
- **Tránsito y peatones:** cada uno lleva un recorrido `{ e, dir, s }` sobre el grafo. Los autos apuntan a un punto adelante en su carril (`CARRIL` por clase), frenan antes de doblar y ceden
  en las esquinas. Los peatones van por la vereda con `side`/`off`. Arriba de la autopista hay tránsito propio (`c.au`).
- **Policía:** cada 1,5 s se calcula la distancia por calle de cada esquina al jugador (`calcDistJugador`). Los patrulleros eligen la salida que más los acerca (`sesgoPolicia`, pueden pegar la vuelta).
  A menos de 30 m y con vista directa van derecho a embestir. Las llamadas y las ambulancias usan `laneTowards`, que arma el recorrido (`plan`) y el punto donde frenar.

- **Controles a pie (estilo GTA):** la cámara manda. Arrastrar gira `player.aim` (continuo); se camina hacia donde mira la cámara.
  ▲ a pie: mantener = caminar (toque corto = unos pasos, `input.fwd`), dos toques rápidos = caminar solo (`player.walking`), otro toque frena (`fwdPress`); en auto/avión ▲ sigue siendo toggle de acelerador. W igual en teclado.
  ▼ caminar atrás mientras se mantiene (en auto: freno/marcha atrás), ◀ ▶ de costado (6,3 m/s), doble toque gira 90° alineado a la calle.
  `player.h` es solo la dirección cardinal derivada (la usan spawns y lógica de calles). Mira `#aim` = punto a 14 m al frente; tiros y golpes van ahí.
  En auto/avión arrastrar es mirada libre (`camLook`) que vuelve sola (con arma de fuego tarda 2,5 s en volver).
- **Disparar desde el auto:** con pistola o metralleta, el botón DISPARAR y la mira siguen en el auto; el tiro sale por la ventana hacia `camYaw + camLook` (`shotDir`), el personaje gira en el asiento y saca el brazo. Los tiros propios no dañan el auto propio.
- **Dos armas de fuego a la vez:** `player.guns` guarda pistola y metralleta, cada una con sus balas; `player.gun` es la que está en la mano. Botón chico `#bW` arriba de DISPARAR (muestra a cuál cambiás) o tecla Q (`swapGun`). Si la de la mano se queda sin balas, cambia sola a la otra. Agarrar del piso un arma que no tenés la suma y la pone en la mano; una que ya tenés solo suma un cargador a esa arma. Las balas de la armería van al arma de la mano.
- **Plata inicial:** se arranca cada partida con $500 (`startGame`; `player.earned` arranca en 0).
- **Negocios robables:** kioscos, almacenes, farmacias, joyerías, casas de cambio (`ce.biz` sorteado por celda, en el frente), minimercado de las nafta,
  supermercados y **3 bancos fijos** (ver "Lugares fijos").
  Interior = escena Three aparte (`room.scene`, `state === 'inside'`); el mundo de afuera se congela.
  Pegar o APUNTAR arranca el asalto; cajeros pagan mientras estés cerca; clientes se tiran, huyen (pueden llamar a la policía) o pelean; guardias disparan.
  Alarma según `BIZ[kind].alarm` → llegan policías adentro; al salir: búsqueda, o sospecha + patrullero despachado al local. Local robado cerrado 150 s.
- **Predios caminables** (iglesia, hospital, escuela, bancos, nafta, súper, zona industrial y patios del puerto): solo bloquea lo que tiene volumen (`obsEspecial`).
  Industrial y puerto se arman al azar, así que sus obstáculos se guardan en la celda (`ce.yard`) al construirla; hasta entonces la celda entera es sólida.
- **Trabajos (taxi y ambulancia)**, sección `jobs` (`JOB_INFO`, `offerJob`, `updateJob`, `drawJob`): al subir a un taxi o ambulancia se ofrece un turno (diálogo `#jobDlg`).
  Cada llamada: punto en una vereda (`jobSpot`), luz amarilla (`beam`, compartida con las picadas) y flecha en `#raceNav`; frenar a menos de 8 m sube al pasajero/herido.
  Taxi: destino al azar 140–330 m, tarifa 25 + 0,22/m, propina 30 % si llegás rápido y sin chocar (`jobBump`). Ambulancia: herido tirado + alguien pidiendo ayuda, tiempo límite, siempre al hospital más cercano (`nearestHospital`), 70 + 0,35/m.
  Bajarse del vehículo termina el turno. Ambulancia = tipo de auto `ambulancia` (estacionada bajo el techito de cada hospital por `parkAmbulances`, y alguna en el tránsito). Las picadas no aparecen durante un turno.
  Hospitales: los 5 fijos de `HOSPITALES` (con lugar para la ambulancia estacionada y el cordón de la puerta).
- **Armas de fuego en el piso:** `spawnPickup` tira 14 % pistolas y 6 % metralletas; policías y bandas desmayados sueltan la pistola el 40 % de las veces.
  Si no tenés arma de fuego, la agarrás con el cargador lleno; si ya tenés, solo suma un cargador a la reserva (tope 5 cargadores; si está llena, queda en el piso).
- **Daño de autos** (sección antes de "guns"): `c.hp`/`c.maxHp` (`carMaxHp`, subido un 30 %: motos 46, común 130, camioneta/ambulancia 154, patrullero 139, colectivo 197). Daño por tiros (pistola 12, metralleta 7, enemigos 4, helicóptero 6),
  choques entre autos (`(fuerza-3)·3`, repartido por peso), paredes (`(fuerza-5)·2`) y postes (6). Bajo 50 % humo gris, bajo 25 % negro; en 0 `explodeCar`:
  radio 6,5 m, desmaya gente, lastima al jugador (2–3 corazones), voltea árboles/faroles, empuja y daña autos cercanos (explosiones en cadena), queda carcasa negra en llamas que no se puede usar.
  Si lo causó el jugador, suma búsqueda. Manejando, el cartel de arriba muestra "DAÑO x %".
- **Llamadas por celular** (sección "phone calls"): un NPC que llama se queda quieto con la mano en la oreja (`p.phone`, celular en `armR`) y dice la frase en globo.
  Ambulancia: si hay un desmayado hace más de 4 s cerca del jugador, el 60 % de las veces alguien llama; llega una ambulancia (`state 'medic'`, para en el carril del lado del herido),
  bajan dos enfermeros (`medicRig`, `p.medic`), se arrodillan y hacen RCP 4,5 s: 60 % se levanta ("¡ME SALVARON!"), 40 % no ("UY... ESTE ESTÁ MUERTO") y se lo llevan. Una a la vez, pausa de 20–35 s entre ambulancias.
  Policía: en `alarm()`, el 30 % de los testigos que huirían llaman (máx. una llamada cada 12 s); al cortar suman 2,5 de sospecha y a los 5–9 s pasa un patrullero (`spawnPatrolCarTowards`) que te reconoce si te ve.
- **Policía:** solo persigue si un policía te ve (o sospecha que se borra sola). Patrulleros: 10,5 + 1,2 × nivel, aceleración 8.
  Presencia reducida: patrullas a pie cada 24–40 s, máximo 2 policías caminando (sin contar guardias de comisaría), 35 % de a dos; en persecución un patrullero nuevo cada 9 s.
  **Helicóptero** (nivel 3) desactivable en Opciones (`settings.heli`).
- **Difusión:** se hizo una imagen promocional para historia de Instagram con ChatGPT (estilo póster de mundo abierto) a partir de capturas verticales sin HUD; para capturas nuevas, ocultar `#hud,#controls,#hint,#zone,#aim,#raceNav,#heist,#enter,.pop` y usar 540×960 con deviceScaleFactor 2.
- Opciones guardadas en `localStorage['calle-brava-settings']`; récord en `localStorage['calle-brava-best']`.

## Pendiente / ideas acordadas para más adelante

- [ ] **Mapa nuevo:** probarlo en juego real y en celular antes de pasarlo a `main`; bajadas intermedias de las autopistas (hoy solo por las puntas y tramos a nivel);
  vereda del lado de afuera en las calles del borde de la ciudad; los autos de la computadora no toman los rulos de los tréboles; la arena se mezcla borrosa con el pasto.
- [ ] **Helicóptero divertido:** hoy solo se lo pierde metiéndose en callejones. Pensar formas de escapar o pelearlo (esconderse bajo techos/túneles, derribarlo, que se vaya tras un tiempo, etc.).
- [ ] **Dificultad de la policía:** seguir afinando con juego real (ya se bajó la velocidad de patrulleros).
- [ ] Opcional: abrir los jardines de barrio residencial y casitas (hoy cerrados por ligustrinas/cercas).
- [ ] Ideas para trabajos: más tipos (policía, bomberos, delivery), racha de viajes con bonus, que los heridos aparezcan después de peleas reales.
- [ ] Idea: que la estación de servicio repare el auto (hoy el daño solo se "cura" cambiando de vehículo).
- [ ] No probado aún: arrastre táctil en celular real, metralleta dentro de los locales, rendimiento en celulares de gama baja (súper y banco grande tienen muchos objetos), entrar con auto a los predios abiertos.
