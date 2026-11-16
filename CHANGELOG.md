# Änderungsprotokoll

Hier steht, was sich in jedem Build geändert hat. Neueste Einträge oben.

## Build 1.1 – Ausgegraute Knöpfe sagen, warum · 16.11.2026

**Neu**
- Ein ausgegrauter Knopf sagt jetzt, warum er gerade nicht geht:
  - **Drüberfahren mit der Maus:** kleiner, gut lesbarer Hinweis (gleiche Schriftgröße wie die Knöpfe,
    gelber Rahmen). Der Mauszeiger wird zum „Verboten“-Zeichen.
  - **Anklicken:** dieselbe kurze Meldung erscheint beim Knopf und verschwindet nach 4 Sekunden von
    selbst. Stand dort vorher eine andere Meldung (z. B. ein Fehler von Uno), ist sie danach wieder da.
    Der Klick löst sonst nichts aus.
- Der Grund passt immer zum gerade aktuellen Zustand, z. B.:
  - Pause: „Pause geht nur, während der Countdown läuft.“
  - Start: „Der Countdown läuft schon.“ bzw. „Der Countdown ist abgelaufen. Erst „Zurück“ drücken,
    dann „Start“.“
  - Einblenden/Ausblenden: „Ist schon eingeblendet.“ / „Ist schon ausgeblendet.“ / „Wird gerade
    umgeschaltet – einen Moment.“
  - Texte übernehmen / Neu laden: „…werden gerade übernommen/geladen“, „Dieses Overlay hat keine Texte
    zum Ändern.“
  - −10/−1/+1/+10 Min: „Bei diesem Overlay lässt sich die Dauer nicht einstellen.“
  - Gleich nach dem Start: „Uno wird noch gelesen – einen Moment.“
  - Aus Zwischenablage einfügen, Titel ändern (Twitch): „…wird gerade eingefügt/geändert“.
- Alle Texte stehen in `einstellungen.toml` (`gesperrt_…`).
- Freie Knöpfe verhalten sich genau wie vorher.

**Hinweis:** Zurzeit gibt es keine Knöpfe für Funktionen, die noch nicht fertig sind. Alle ausgegrauten
Knöpfe gehören zu fertigen Funktionen und sind nur im Moment gesperrt. Alle 9, die gesperrt werden
können, haben jetzt einen Hinweis.

**Behoben (beim Prüfen gefunden)**
- Ist der Countdown abgelaufen, meldet Uno ihn weiter als „läuft“. Der Hinweis am Start-Knopf hätte
  deshalb „läuft schon“ gesagt – jetzt sagt er richtig „abgelaufen, erst Zurück drücken“.

**Geprüft**
- 195 automatische Tests (13 neu), dreimal hintereinander ohne Fehler; die neuen zusätzlich
  15-mal, drei gleichzeitig unter Last.
- **Kein Knopf vergessen:** Ein Test liest den Programmtext und findet jede Stelle, an der ein Knopf
  gesperrt wird – jeder davon muss einen Hinweis haben. Ein zweiter Test geht durch viele Zustände
  (bereit, läuft, abgelaufen, im Stream, schaltet gerade, Uno wird gelesen, Texte laden/übernehmen,
  Uno einfügen) und prüft jeden sichtbaren ausgegrauten Knopf im ganzen Fenster: Hinweis da, passend
  (nicht nur „geht gerade nicht“), Mauszeiger „Verboten“.
- Gegenprobe: Hinweis an „Pause“ entfernt → beide Tests schlagen fehl; einen neuen gesperrten Knopf
  ohne Hinweis eingebaut → der Programmtext-Test schlägt fehl.
- Aussehen mit Standbildern geprüft.

## Build 1.1 – Countdown-Zeit direkt eintippen · 16.11.2026

**Neu**
- Einfach auf die große Countdown-Zeit klicken (Doppelklick geht auch), die neue Zeit eintippen, Enter –
  fertig. Die alte Zeit ist schon markiert, man tippt also einfach drüber. Esc oder Wegklicken bricht ab.
- **Ohne Enter und Esc:** Neben dem Eingabefeld stehen zwei große Knöpfe, so hoch wie das Feld –
  grün mit Häkchen ✓ „Übernehmen“ (wie Enter) und rot mit Kreuz ✕ „Abbrechen“ (wie Esc). Sie sind nur
  zu sehen, solange getippt wird. Ein Klick darauf zählt **nicht** als Wegklicken: das Feld bleibt
  offen, bis der Knopf wirkt. Falsche Eingaben fängt ✓ genauso ab wie Enter (Hinweis in Rot, Feld bleibt
  offen, die falsche Eingabe ist markiert und wird beim Weitertippen ersetzt). Enter und Esc gehen weiter.
- Was man tippen kann: `5:00`, `12:30`, `90:00`, `1:05:00` – oder nur `5` für 5 Minuten.
  `5.30` und `5,30` gehen auch. Höchstens 9:59:59 (wie bei den Knöpfen, `einstellungen.toml`).
- **Im Stream gesperrt:** Ist der Countdown gerade eingeblendet (Lampe rot), öffnet ein Klick kein Feld,
  sondern zeigt kurz „Der Countdown ist gerade im Stream. Zum Ändern der Zeit erst ausblenden.“ –
  der Hinweis verschwindet nach 4 Sekunden von selbst. Wird eingeblendet, während man noch tippt,
  geht das Feld zu und nichts wird übernommen.
- Vertippt? Buchstaben, `5:75`, `0:00` oder zu lang gibt einen kurzen Hinweis in Rot, das Feld bleibt
  offen zum Verbessern. Es wird nichts an Uno geschickt.
- Die Knöpfe „−10 / −1 / +1 / +10 Min“ bleiben und arbeiten mit derselben Zeit: erst `12:30` tippen,
  dann „+1 Min“ ergibt 13:30.
- Wenn der Countdown schon gelaufen ist (angehalten oder abgelaufen), steht er nach dem Eintippen
  genau auf der neuen Zeit und ist wieder „Bereit“. Das geht als **ein** Befehl an Uno (neue Dauer
  `BeginTime` + Zurücksetzen), damit Overlay und OpenRegie dieselbe Zeit zeigen.
- Nimmt Uno die neue Zeit nicht an, zeigt OpenRegie wieder die alte Zeit (nichts vorgaukeln).

**Behoben (beim Prüfen gefunden)**
- Knöpfe ✓/✕: Beim ersten Versuch ging das Feld schon beim *Drücken* eines der Knöpfe zu – Qt gibt den
  Fokus bei einem Klick an das nächste übergeordnete Element weiter, das Feld verlor ihn und das galt
  als Wegklicken. Jetzt reicht der Rahmen um Feld und Knöpfe den Fokus ans Feld zurück.
- Ein schneller Doppelklick auf ✓ schickt die Zeit nur einmal an Uno.
- Klickt man schnell hintereinander (z. B. „+1 Min“ und gleich danach eine Zeit eintippen), konnte eine
  verspätete Antwort von Uno die Anzeige kurz auf die alte Zeit zurückdrehen – und der nächste
  „±1 Min“-Klick rechnete dann mit der falschen Zeit. Jetzt zählt nur noch die Antwort zur neuesten
  Änderung. Das gilt auch für die Minuten-Knöpfe.
- Test „Neustart mit Einzel-Uno“: Er klickte „Ausblenden“, bevor die Antwort auf „Einblenden“ im
  Fenster angekommen war, und schlug deshalb ab und zu fehl (auch schon vorher, 2 von 10 Läufen).
  Nur der Test wartet jetzt richtig, am Programm hat sich dafür nichts geändert.

**Geprüft**
- 182 automatische Tests (25 neu), dreimal hintereinander ohne Fehler; die neuen Countdown-Tests
  zusätzlich viele Male, auch drei gleichzeitig unter Last (Knöpfe ✓/✕: 30 von 30 Läufen).
- Neu für die Knöpfe: ✓ übernimmt, ✕ bricht ab, alle falschen Eingaben mit ✓, ✕ räumt den Hinweis weg,
  ✓ nach dem Einblenden schickt nichts, Doppelklick auf ✓ schickt nur einmal, Größe und Platz (passen
  neben das Feld in die Spalte, auch „1:05:00“). Gegenprobe: ohne die Fokus-Korrektur schlagen die
  Knopf-Tests genau mit dem gefundenen Fehler fehl, ohne den Doppelklick-Schutz der Doppelklick-Test.
- Neu u. a.: Eintippen kommt bei Uno an, Esc, alle falschen Eingaben, gesperrt im Stream mit Hinweis,
  der von selbst verschwindet, live geschaltet während des Tippens, Doppelklick, nur Tastatur,
  angehaltener Countdown, Uno lehnt ab, verspätete Antwort (Gegenprobe: ohne Korrektur schlägt der
  Test genau mit dem gefundenen Fehler fehl).
- Aussehen mit Standbildern geprüft: Eingabefeld genauso groß wie die Zeit, Hinweise schieben nichts
  übereinander.
- **Mit dem echten Uno geprüft: 13 von 13.** Eintippen kommt an (Uno speichert genau die Sekunden),
  Dauer + Zurücksetzen in einem Befehl nimmt Uno an (Zeitgeber steht danach auf Anfang und läuft nicht
  los), OpenRegie zeigt dieselbe Zeit wie Uno. Danach alte Dauer (4:48:40) wiederhergestellt, Countdown
  blieb die ganze Zeit ausgeblendet.
- **Knöpfe ✓/✕ mit dem echten Uno geprüft: 20 von 20.** ✓ übernimmt, Feld bleibt beim Drücken offen,
  fünf falsche Eingaben mit ✓ kommen nicht bei Uno an, ✕ ändert nichts, Enter und Esc gehen weiter,
  OpenRegie und Uno zeigen dieselbe Zeit. Countdown die ganze Zeit ausgeblendet, danach Dauer 4:50
  wiederhergestellt.

## Build 1.1 – Korrektur: Countdown blendet in der Mitte aus · 14.11.2026

**Behoben**
- Beim Ausblenden verschwand nur der Hintergrund – die drei Kreise mit „HOURS / MINUTES / SECONDS“
  blieben in der Mitte stehen. Selbst geprüft mit einem eigenen Test-OBS und Standbildern der echten
  Uno-Ausgabe: Der eigentliche Ein/Aus-Schalter dieses Unos ist das Häkchen „ShowOverlay“ (dasselbe
  setzen „HideOverlay“ und der Aus-Schalter in Uno). Die Teile auf „Out“ zu stellen, entfernt nur den
  Hintergrund.
- Jetzt: **Einblenden** = Teile auf „In“ + „Active“ an + „ShowOverlay“ an.
  **Ausblenden** = nur „ShowOverlay“ aus – Hintergrund und Countdown blenden zusammen sanft an Ort und
  Stelle aus (nach etwa 0,5 Sekunden ist alles weg).
- Das Tally-Licht beachtet den Uno-Schalter: Wird in Uno selbst ausgeschaltet, geht die Lampe aus.

**Geprüft**
- 157 automatische Tests; das nachgeahmte Uno zeigt jetzt wie das echte „nur Kreise“, wenn nur die
  Teile ausgeblendet werden (Gegenprobe zum Fehler).
- Mit dem echten Uno und eigenem Test-OBS: OpenRegie blendet ein (volles Bild), aus (nach 0,5 s leer),
  wieder ein und wieder aus – jeweils mit Standbild geprüft, Tally-Licht stimmt.

## Build 1.1 – Uno-Overlays in OBS immer ganz oben · 14.11.2026

**Behoben**
- Der Countdown war im Stream nicht zu sehen. Ursache: In OBS lag die Bildschirmaufnahme über der
  Countdown-Quelle – und diese Quelle war noch die alte „Rolliregie Countdown“ aus Build 1.0
  (Adresse `http://127.0.0.1:8787/countdown` gibt es seit 1.1 nicht mehr, sie blieb leer).
  Eine Quelle mit der Uno-Ausgabe gab es in OBS gar nicht.

**Neu**
- OpenRegie kümmert sich selbst um die Uno-Quellen in OBS (beim Verbinden und bei jeder Änderung in OBS):
  - Für jedes Uno-Projekt gibt es automatisch in **jeder Szene** eine Browserquelle „Uno: <Name>“ mit der
    Ausgabe-Adresse von Uno, so groß wie das Bild. Neue Szenen bekommen sie auch.
  - **Uno-Quellen liegen immer ganz oben.** Kommt in OBS eine Quelle dazu oder wird etwas darüber
    geschoben, rückt OpenRegie die Overlays sofort wieder nach oben. Die übrige Reihenfolge bleibt.
  - Auch von Hand angelegte Uno-Quellen werden erkannt (an der Uno-Ausgabe-Adresse) – nichts doppelt.
  - Die alte, leere Quelle „Rolliregie Countdown“ wird einmal entfernt (nur diese, sonst nichts).
  - Abschaltbar in `einstellungen.toml`: `[obs] uno_in_jede_szene`, `[obs] overlays_immer_oben`.

**Geprüft**
- 155 automatische Tests, zweimal ohne Fehler; neu u. a. genau Kevins Szene, neue Quelle kommt dazu,
  von Hand darübergeschoben, neue Szene, Neuverbinden ohne Doppel, keine Endlosschleife, Oberfläche flüssig.
- 26 von 26 Prüfungen mit echtem OBS 33.0.1 (getrenntes Test-OBS), davon 7 neu für die Uno-Quellen.
- Echter Start mit Kevins OBS: alte Quelle entfernt, „Uno: Countdown | Circles“ (1920 × 1080) liegt
  in „Szene“ ganz oben über der Bildschirmaufnahme.

## Build 1.1 – Korrektur: Neustart mit Einzel-Uno, Regiepult friert nie ein · 14.11.2026

**Behoben**
- Nach dem Neustart zeigte „Ausgewählt“ zweimal „Overlays.uno ist gerade nicht erreichbar“,
  „Zustand unbekannt“, leere Texte – und reagierte auf keinen Knopf mehr.
  Ursache (im Protokoll und im Nachbau gefunden, NICHT Uno): Beim Start steht das Einzel-Uno erst als
  Platzhalter in der Liste, bis Uno geantwortet hat. OpenRegie legte danach ein *neues* Overlay an,
  statt den Platzhalter zu füllen – „Ausgewählt“ hing weiter am leeren Platzhalter, und jeder Klick
  endete mit der irreführenden Meldung „nicht erreichbar“. Uno hat beim Start keinen einzigen Befehl
  abgelehnt; die Abfrage beim Start nutzt nur Befehle, die Einzel-Unos verstehen
  (`GET …`, `…/model`, `…/control` – mit der echten Adresse geprüft).
  Jetzt wird das Overlay immer an Ort und Stelle gefüllt; zusätzlich ein Sicherheitsnetz im Fenster.
- Solange ein Uno noch gelesen wird, steht „Wird geladen …“ da und die Knöpfe sind still aus –
  keine rote Meldung mehr.

**Meldungen sauber getrennt**
- Keine Verbindung oder Zeitüberschreitung → „Overlays.uno ist gerade nicht erreichbar“.
- 404 bzw. ungültiger Schlüssel → „Uno kennt diese Adresse nicht“.
- 400 „Invalid command“ → diese Funktion kann das Uno nicht: wird still ausgegraut, keine rote Meldung.
- Meldungen zur Erreichbarkeit stehen EINMAL unter der Bibliothek, nicht zusätzlich im Bedienfeld,
  und dieselbe Meldung kommt nie zweimal hintereinander. Ist Uno wieder da, verschwindet sie von selbst.
- Ist Uno nicht erreichbar, werden die Lampen der Kacheln grau („Aus“).

**Ein Regiepult friert nie ein**
- Uno wartet höchstens 5 Sekunden auf eine Antwort (`[uno] zeitlimit_sekunden`), danach „nicht erreichbar“.
  Internet-Anfragen liefen schon vorher ohne Warten der Oberfläche.
- Der Passwortspeicher (`secret-tool`) lief bisher im Haupt-Thread und konnte das Fenster bis zu
  30 Sekunden einfrieren, z. B. wenn KDE-Wallet nach dem Passwort fragt. Jetzt läuft er in einem
  eigenen Hintergrund-Thread (Uno und Twitch), Speichern in fester Reihenfolge.

**Geprüft**
- 142 automatische Tests, zweimal ohne Fehler. Neu: Neustart mit eingefügtem Einzel-Uno (genau der
  gemeldete Ablauf), Uno antwortet gar nicht, Klick während Uno hängt, Passwortspeicher hängt,
  Uno lehnt Befehle mit 400 ab, Adresse wird ungültig. In allen Fällen wird gemessen, dass die
  Oberfläche flüssig bleibt (längste Pause unter 0,25 s; Gegenprobe: ein echtes Hängen wird erkannt).
- Neustart gegen das echte „Countdown | Circles“ (nur lesend): keine Meldung, keine Ablehnung,
  alles bereit, längste Pause 21 ms. Echter Programmstart: Protokoll ohne Fehler.

## Build 1.1 – Einzel-Unos richtig steuern, neues Aussehen · 14.11.2026

**Behoben**
- Einzel-Unos (z. B. „Countdown | Circles“) ließen sich zwar einfügen, aber nicht ein- und ausblenden.
  Mit dem echten Uno herausgefunden: Einzel-Unos verstehen über `…/api` keinen Befehl außer
  „ShowOverlay“/„HideOverlay“ – und die zeigen nichts an. Gesteuert werden sie über die
  Singular-Schnittstelle derselben Adresse (`…/control`, `…/model`).
- Komplett sichtbar wird ein Einzel-Uno erst, wenn Hauptteil und alle Teile, die im Uno-Bauplan von
  Haus aus an sind, auf „In“ gehen und das Häkchen „Active“ an ist (sonst nur Kreis ohne Zahlen).
  Genau das macht OpenRegie jetzt mit einem Klick – beim Ausblenden alles zurück.
- Beim Start war kein Overlay ausgewählt, solange die Liste noch lud.

**Neu**
- Einzel-Unos zeigen ihren echten Namen und ihr Vorschaubild aus Uno.
- **Countdown steuern** (bei Uno-Overlays mit Zeitgeber): große Anzeige der Restzeit, die mitläuft,
  Knöpfe Start, Pause, Zurück und Dauer −10 Min / −1 Min / +1 Min / +10 Min.
- Textfelder von Einzel-Unos (z. B. „Message“ = Endtext des Countdowns) lassen sich ändern.
- Tally-Licht auch bei Einzel-Unos, abgelesen aus Uno.
- **Neues Aussehen nach dem Entwurf „Hauptfenster“:**
  - Kopfleiste mit gelbem Logo, rundem OBS-Schild, rotem „● ON AIR“-Schild und Uhr.
  - Links die **Bibliothek** mit Kacheln (Vorschau bzw. Countdown-Zeit). Der farbige Rahmen ist die
    Lampe: rot = Live, grün = Bereit, grau = Aus – mit Erklärung „LAMPEN“ darunter.
  - In der Mitte das **Live-Bild** mit rotem Rahmen, solange gesendet wird; darunter der Twitch-Titel.
  - Rechts **AUSGEWÄHLT** mit Countdown, Texten und unten den großen Knöpfen
    „▶ Einblenden“ (grün) und „■ Ausblenden“ (rot).
  - Schriftart steht jetzt in `einstellungen.toml` (`[groessen] schriftart`).
- Aus dem Entwurf bewusst noch nicht übernommen: Suche, Playlist, Akzentfarbe, „Ausblenden nach“,
  Quellen aus OBS (Build 1.2) und Doppelklick (nur einfacher Klick).
- `werkzeuge/test_mit_echtem_uno.py`: prüft OpenRegie gegen das echte Einzel-Uno.

**Geändert**
- Uno wird nur noch alle 20 Sekunden nach dem Zustand gefragt (Uno erlaubt 10.000 Anfragen am Tag).
  Nach jedem eigenen Klick stimmt die Lampe sofort.

**Geprüft**
- 133 automatische Tests, mehrfach ohne Fehler. Das nachgeahmte Uno verhält sich wie das echte
  (auch „Kreis ohne Zahlen“ ohne „Active“ und „ShowOverlay zeigt nichts“).
- 19 von 19 Prüfungen mit dem **echten** „Countdown | Circles“: Einfügen, Name, Vorschaubild,
  Ein-/Ausblenden komplett, Start/Pause/Zurück, Restzeit sekundengenau, Dauer ändern und zurück.
  Danach war alles wieder wie vorher (ausgeblendet, 4:59:40).

## Build 1.1 – Korrektur: Einzel-Unos · 14.11.2026

**Behoben**
- Ein einzelnes Uno-Overlay (z. B. „Countdown | Circles“) ließ sich nicht einfügen: Es kam immer
  „Uno kennt diese Adresse nicht“, obwohl die Adresse stimmte.
  Ursache: OpenRegie prüfte die Adresse mit dem Befehl „GetOverlays“ und wertete *jede* Ablehnung als
  „Adresse unbekannt“. Einzel-Unos kennen „GetOverlays“ nicht und antworten mit
  HTTP 400 „Invalid command: GetOverlays“ – die Adresse ist dabei gültig.
- Jetzt gilt:
  - „Invalid command“ = Adresse gültig. Das Uno wird als **Einzel-Uno** erkannt und erscheint als ein
    Overlay („Uno-Overlay 1“) in der Liste. Befehle an Einzel-Unos gehen ohne Overlay-Kennung.
  - Nur ein echtes „nicht gefunden“ (HTTP 404) bzw. ein ungültiger Schlüssel (401/403) zeigt
    „Uno kennt diese Adresse nicht“.
  - Kein Internet oder eine Störung bei Uno werden als solche gemeldet, nicht mehr als „Adresse unbekannt“.
  - Einzel-Unos werden nicht alle 5 Sekunden abgefragt (schont das Anfrage-Limit von Uno).
  - Schon gespeicherte Einzel-Unos werden beim nächsten Start von selbst erkannt.

**Neu**
- `werkzeuge/uno_pruefen.py`: fragt ein echtes Uno, welche Befehle es versteht (nur Lese-Befehle,
  Ein-/Ausblenden nur mit `--zeigen`). Die Adresse steht nur in `daten/geheim.toml` (nicht in Git).

**Geprüft**
- 118 automatische Tests (12 neu), zweimal hintereinander ohne Fehler. Das nachgeahmte Uno kennt jetzt
  auch Einzel-Unos, die „GetOverlays“ genau wie das echte mit 400 „Invalid command“ ablehnen.
- Gegenprobe: Die neuen Tests schlagen mit dem alten Code fehl.
- Noch offen: Befehle eines echten Einzel-Unos (Tally-Zustand, Countdown Play/Reset/Dauer).

## Build 1.1 – erste Version zum Streamen · 14.11.2026

**Neu**
- Neuer Name: **OpenRegie** – „Profi-Regie für alle. Einfach live.“ (Programm, Fenster, Startmenü, Protokoll).
- Ladebildschirm beim Start: zeigt, was gerade passiert („OBS wird im Hintergrund gestartet …“).
- Build-Anzeige als dezentes Wasserzeichen unten links: „OpenRegie · Vorabversion · Build 1.1“.
- **OBS unsichtbar im Hintergrund:**
  - OpenRegie startet OBS selbst, nur als Symbol in der Taskleiste, ohne OBS-Fenster.
  - Verbindet sich von selbst und lädt die Szenensammlung aus `einstellungen.toml` (`[obs] szenensammlung`).
  - Läuft OBS schon, wird kein zweites gestartet (und es wird später auch nicht beendet).
  - Beim Schließen von OpenRegie wird das mitgestartete OBS sauber beendet.
    Ist man gerade live, fragt OpenRegie vorher nach und beendet erst den Stream.
  - Klare Meldungen: OBS startet nicht, OBS ist abgestürzt, OBS meldet sich nicht, Szenensammlung fehlt –
    jeweils mit den Knöpfen „OBS starten“ und „Neu verbinden“.
- **Overlays.uno:**
  - Uno-Projekt mit einem Klick auf „Aus Zwischenablage einfügen“ hinzufügen (API-Adresse aus Uno).
  - Die Adresse wird nur im Passwortspeicher des Systems gespeichert, nie als lesbarer Text.
  - Einfache Liste aller Overlays mit Tally-Licht (rot = im Stream) und Knopf „Ein“/„Aus“.
  - Bedienfeld pro Overlay: großer Knopf „Einblenden“/„Ausblenden“ und alle Texte zum Ändern.
  - Das Tally-Licht folgt auch, wenn in Uno selbst ein- oder ausgeblendet wird.
  - Neue Overlays aus Uno erscheinen mit „Liste neu laden“. Mehrere Uno-Projekte sind möglich.
  - Projekt entfernen mit zwei Klicks („Entfernen“ → „Wirklich entfernen?“).
- **Twitch:**
  - „Mit Twitch anmelden“: OpenRegie zeigt einen Code und öffnet die Twitch-Seite, dort „Autorisieren“ klicken.
    Kein geheimer Schlüssel im Code (Device Code Flow, nur öffentliche Client-ID).
  - Streamtitel direkt in OpenRegie ändern (höchstens 140 Zeichen).
  - Die Anmeldung wird von selbst verlängert. Twitch erlaubt das bei Open-Source-Apps höchstens 30 Tage,
    danach meldet OpenRegie „Bitte neu anmelden“.

**Entfernt**
- Der eigene Countdown aus Build 1.0 (lokale Seite und Knopf „Countdown in OBS einrichten“).
  Alle Grafiken, auch Uhr und Countdown, kommen jetzt von Overlays.uno.

**Geprüft**
- 106 automatische Tests mit nachgeahmtem OBS, nachgeahmtem Overlays.uno und nachgeahmtem Twitch.
- 19 Prüfungen mit echtem OBS 33.0.1 in einem getrennten Test-OBS (`werkzeuge/test_mit_echtem_obs.py`):
  unsichtbarer Start (kein OBS-Fenster laut KDE), Szenensammlung beim Start und per Fernsteuerung,
  Vorschau, On Air, Absturz und Neustart, sauberes Beenden.
- Echter Start mit dem eigenen OBS: OBS unsichtbar, nach etwa 3 Sekunden verbunden, beim Schließen beendet.
- Noch offen: Prüfung mit dem echten Overlays.uno-Konto und der echten Twitch-Anmeldung.

## Build 1.0 – Motortest (intern) · 10.11.2026

**Neu**
- Eigenes Programmfenster im Regiepult-Look (dunkel, große Knöpfe, nur einfacher Klick).
- Verbindung zu OBS über den OBS-WebSocket:
  - Port und Passwort werden automatisch aus den OBS-Einstellungen gelesen, man muss nichts eintippen.
  - Große Statuslampe: grün „OBS verbunden“, gelb „Verbinde …“, rot „Keine Verbindung“.
  - Bricht die Verbindung ab, verbindet sich Rolliregie von selbst neu.
  - Verständliche Hinweise, z. B. „OBS ist nicht geöffnet“ oder „Fernsteuerung ist aus“, dazu die Knöpfe „OBS starten“ und „Neu verbinden“.
- Live-Vorschau des Sendebilds: etwa 10 Einzelbilder pro Sekunde über den WebSocket, ohne virtuelle Kamera.
- Rotes „ON AIR“-Licht, solange OBS streamt (orange beim Starten und Stoppen).
- Countdown: Dauer mit −1 Min, +1 Min, −10 Sek und +10 Sek einstellen, dazu Start/Weiter, Pause und Stopp.
  - Erscheint in OBS über eine lokale Seite (`http://127.0.0.1:8787/countdown`).
  - Knopf „Countdown in OBS einrichten“ legt die Browserquelle mit einem Klick in der gesendeten Szene an.
  - Position, Schrift, Farben und Endtext („Gleich geht's los!“) stehen in `einstellungen.toml`.
- Liste der Rolliregie-Titel (zunächst nur der Countdown).
- Build-Anzeige unten links („Rolliregie Build 1.0“). Die Nummer steht nur in der Datei `VERSION`.
- Startmenü-Eintrag mit eigenem Symbol (`werkzeuge/startmenue_einrichten.sh`).
- Es kann nur ein Rolliregie-Fenster gleichzeitig offen sein.
- Protokolldatei für die Fehlersuche: `~/.local/state/rolliregie/rolliregie.log`.

**Geprüft**
- 93 automatische Tests mit einem nachgeahmten OBS, mehrfach hintereinander ohne Fehler.
- 12 Prüfungen mit echtem OBS 33.0.1 (WebSocket 5.7.6) in einem getrennten Test-OBS
  (`werkzeuge/test_mit_echtem_obs.py`): Vorschau mit 10 Bildern pro Sekunde bei etwa 5 % Last für OBS.
