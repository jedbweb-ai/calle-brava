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

## Mapa del código (secciones del `<script>`, en orden)

ciudad/grilla (`P=48`, `HALF=10`, `districtOf`, `zoneOf`, `specialOf`, `BANKS`, `lotObs`, `clampWalk`, `solidAt`) →
renderer y texturas en canvas → edificios por zona (`buildCentro`, `buildTowers`, `buildSpecial`, `buildBank`…) → `makeBlock`/`updateBlocks`
(la ciudad se genera por cuadras alrededor del jugador) → armas → personajes (`makePerson`, `randomRig`) → jugador → peatones →
autos → efectos/sonido (`sfx`) → combate (`startAttack`, `resolveHit`, `poseAttack`) → HUD/minimapa/mapa grande → input →
armería → armas de fuego → picadas → bandas → policía (`addHeat`, `policeDrive`, `updatePolice`, `dispatches`) → helicóptero →
aeropuerto/aviones → **negocios y robos** (`BIZ`, `bizOf`, `buildRoom`, `enterBiz`/`leaveBiz`, `startHeist`, `updateRoom*`) →
**trabajos** (`JOB_INFO`, `jobSpot`, `updateJob`, ambulancia) → pausa/opciones → estado de juego → `frame()`.

## Cómo está hecho hoy (decisiones ya tomadas)

- **Controles a pie (estilo GTA):** la cámara manda. Arrastrar gira `player.aim` (continuo); se camina hacia donde mira la cámara.
  ▲ a pie: mantener = caminar (toque corto = unos pasos, `input.fwd`), dos toques rápidos = caminar solo (`player.walking`), otro toque frena (`fwdPress`); en auto/avión ▲ sigue siendo toggle de acelerador. W igual en teclado.
  ▼ caminar atrás mientras se mantiene (en auto: freno/marcha atrás), ◀ ▶ de costado (6,3 m/s), doble toque gira 90° alineado a la calle.
  `player.h` es solo la dirección cardinal derivada (la usan spawns y lógica de calles). Mira `#aim` = punto a 14 m al frente; tiros y golpes van ahí.
  En auto/avión arrastrar es mirada libre (`camLook`) que vuelve sola (con arma de fuego tarda 2,5 s en volver).
- **Disparar desde el auto:** con pistola o metralleta, el botón DISPARAR y la mira siguen en el auto; el tiro sale por la ventana hacia `camYaw + camLook` (`shotDir`), el personaje gira en el asiento y saca el brazo. Los tiros propios no dañan el auto propio.
- **Dos armas de fuego a la vez:** `player.guns` guarda pistola y metralleta, cada una con sus balas; `player.gun` es la que está en la mano. Botón chico `#bW` arriba de DISPARAR (muestra a cuál cambiás) o tecla Q (`swapGun`). Si la de la mano se queda sin balas, cambia sola a la otra. Agarrar del piso un arma que no tenés la suma y la pone en la mano; una que ya tenés solo suma un cargador a esa arma. Las balas de la armería van al arma de la mano.
- **Plata inicial:** se arranca cada partida con $500 (`startGame`; `player.earned` arranca en 0).
- **Negocios robables:** kioscos, almacenes, farmacias, joyerías, casas de cambio (fachadas por `bizOf`, deterministas), minimercado de las nafta,
  supermercados y **3 bancos fijos**: chico `(-1,-1)` centro, mediano `(5,2)` paseo, grande `(6,-5)` microcentro.
  Interior = escena Three aparte (`room.scene`, `state === 'inside'`); el mundo de afuera se congela.
  Pegar o APUNTAR arranca el asalto; cajeros pagan mientras estés cerca; clientes se tiran, huyen (pueden llamar a la policía) o pelean; guardias disparan.
  Alarma según `BIZ[kind].alarm` → llegan policías adentro; al salir: búsqueda, o sospecha + patrullero despachado al local. Local robado cerrado 150 s.
- **Predios caminables** (iglesia, hospital, escuela, bancos, nafta, súper, zona industrial y patios del puerto): solo bloquea lo que tiene volumen (`lotObs`).
  Industrial y puerto se arman al azar, así que sus obstáculos (galpones, contenedores, tanques, chimeneas, cercas) se guardan en `yardObs` al construir la cuadra.
- **Trabajos (taxi y ambulancia)**, sección `jobs` (`JOB_INFO`, `offerJob`, `updateJob`, `drawJob`): al subir a un taxi o ambulancia se ofrece un turno (diálogo `#jobDlg`).
  Cada llamada: punto en una vereda (`jobSpot`), luz amarilla (`beam`, compartida con las picadas) y flecha en `#raceNav`; frenar a menos de 8 m sube al pasajero/herido.
  Taxi: destino al azar 140–330 m, tarifa 25 + 0,22/m, propina 30 % si llegás rápido y sin chocar (`jobBump`). Ambulancia: herido tirado + alguien pidiendo ayuda, tiempo límite, siempre al hospital más cercano (`nearestHospital`), 70 + 0,35/m.
  Bajarse del vehículo termina el turno. Ambulancia = tipo de auto `ambulancia` (estacionada bajo el techito de cada hospital por `parkAmbulances`, y alguna en el tránsito). Las picadas no aparecen durante un turno.
  Hospitales: 3 por sorteo al este + 2 fijos al oeste (`HOSPITALS`: barrio `(-5,-3)` y centro `(-2,-5)`).
- **Armas de fuego en el piso:** `spawnPickup` tira 14 % pistolas y 6 % metralletas; policías y bandas desmayados sueltan la pistola el 40 % de las veces.
  Si no tenés arma de fuego, la agarrás con el cargador lleno; si ya tenés, solo suma un cargador a la reserva (tope 5 cargadores; si está llena, queda en el piso).
- **Daño de autos** (sección antes de "guns"): `c.hp`/`c.maxHp` (`carMaxHp`, subido un 30 %: motos 46, común 130, camioneta/ambulancia 154, patrullero 139, colectivo 197). Daño por tiros (pistola 12, metralleta 7, enemigos 4, helicóptero 6),
  choques entre autos (`(fuerza-3)·3`, repartido por peso), paredes (`(fuerza-5)·2`) y postes (6). Bajo 50 % humo gris, bajo 25 % negro; en 0 `explodeCar`:
  radio 6,5 m, desmaya gente, lastima al jugador (2–3 corazones), voltea árboles/faroles, empuja y daña autos cercanos (explosiones en cadena), queda carcasa negra en llamas que no se puede usar.
  Si lo causó el jugador, suma búsqueda. Manejando, el cartel de arriba muestra "DAÑO x %".
- **Policía:** solo persigue si un policía te ve (o sospecha que se borra sola). Patrulleros: 10,5 + 1,2 × nivel, aceleración 8.
  **Helicóptero** (nivel 3) desactivable en Opciones (`settings.heli`).
- **Difusión:** se hizo una imagen promocional para historia de Instagram con ChatGPT (estilo póster de mundo abierto) a partir de capturas verticales sin HUD; para capturas nuevas, ocultar `#hud,#controls,#hint,#zone,#aim,#raceNav,#heist,#enter,.pop` y usar 540×960 con deviceScaleFactor 2.
- Opciones guardadas en `localStorage['calle-brava-settings']`; récord en `localStorage['calle-brava-best']`.

## Pendiente / ideas acordadas para más adelante

- [ ] **Helicóptero divertido:** hoy solo se lo pierde metiéndose en callejones. Pensar formas de escapar o pelearlo (esconderse bajo techos/túneles, derribarlo, que se vaya tras un tiempo, etc.).
- [ ] **Dificultad de la policía:** seguir afinando con juego real (ya se bajó la velocidad de patrulleros).
- [ ] Opcional: abrir los jardines de barrio residencial y casitas (hoy cerrados por ligustrinas/cercas).
- [ ] Ideas para trabajos: más tipos (policía, bomberos, delivery), racha de viajes con bonus, que los heridos aparezcan después de peleas reales.
- [ ] Idea: que la estación de servicio repare el auto (hoy el daño solo se "cura" cambiando de vehículo).
- [ ] No probado aún: arrastre táctil en celular real, metralleta dentro de los locales, rendimiento en celulares de gama baja (súper y banco grande tienen muchos objetos), entrar con auto a los predios abiertos.
