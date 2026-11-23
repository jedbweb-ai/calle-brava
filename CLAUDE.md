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
pausa/opciones → estado de juego → `frame()`.

## Cómo está hecho hoy (decisiones ya tomadas)

- **Controles a pie (estilo GTA):** la cámara manda. Arrastrar gira `player.aim` (continuo); se camina hacia donde mira la cámara.
  ▲ toggle caminar, ▼ caminar atrás mientras se mantiene (en auto: freno/marcha atrás), ◀ ▶ de costado (6,3 m/s), doble toque gira 90° alineado a la calle.
  `player.h` es solo la dirección cardinal derivada (la usan spawns y lógica de calles). Mira `#aim` = punto a 14 m al frente; tiros y golpes van ahí.
  En auto/avión arrastrar es mirada libre (`camLook`) que vuelve sola.
- **Negocios robables:** kioscos, almacenes, farmacias, joyerías, casas de cambio (fachadas por `bizOf`, deterministas), minimercado de las nafta,
  supermercados y **3 bancos fijos**: chico `(-1,-1)` centro, mediano `(5,2)` paseo, grande `(6,-5)` microcentro.
  Interior = escena Three aparte (`room.scene`, `state === 'inside'`); el mundo de afuera se congela.
  Pegar o APUNTAR arranca el asalto; cajeros pagan mientras estés cerca; clientes se tiran, huyen (pueden llamar a la policía) o pelean; guardias disparan.
  Alarma según `BIZ[kind].alarm` → llegan policías adentro; al salir: búsqueda, o sospecha + patrullero despachado al local. Local robado cerrado 150 s.
- **Edificios especiales** (iglesia, hospital, escuela, bancos, nafta, súper): el predio es caminable, solo el edificio bloquea (`lotObs`).
- **Policía:** solo persigue si un policía te ve (o sospecha que se borra sola). Patrulleros: 10,5 + 1,2 × nivel, aceleración 8.
  **Helicóptero** (nivel 3) desactivable en Opciones (`settings.heli`).
- Opciones guardadas en `localStorage['calle-brava-settings']`; récord en `localStorage['calle-brava-best']`.

## Pendiente / ideas acordadas para más adelante

- [ ] **Helicóptero divertido:** hoy solo se lo pierde metiéndose en callejones. Pensar formas de escapar o pelearlo (esconderse bajo techos/túneles, derribarlo, que se vaya tras un tiempo, etc.).
- [ ] **Dificultad de la policía:** seguir afinando con juego real (ya se bajó la velocidad de patrulleros).
- [ ] Opcional: abrir los jardines de barrio residencial y casitas (hoy cerrados por ligustrinas/cercas).
- [ ] No probado aún: arrastre táctil en celular real, metralleta dentro de los locales, rendimiento en celulares de gama baja (súper y banco grande tienen muchos objetos), entrar con auto a los predios abiertos.
