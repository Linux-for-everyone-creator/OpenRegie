# Änderungsprotokoll

Hier steht, was sich in jedem Build geändert hat. Neueste Einträge oben.

## Build 1.2.2 – Countdown wieder flott, „Shot hinzufügen“ im eigenen Fenster · 23.11.2026

**Kurz gesagt:** Der Countdown hing auf 00:00 fest und „Start“ war grau. Das ist jetzt behoben. Und die
Auswahl „Shot hinzufügen“ (Kamera, Spiel, Reactions, Bildschirm, Bild) poppt jetzt als eigenes Fenster
auf, so wie „Add Input“ bei vMix. Rechts bleibt dabei dein Countdown einfach stehen.

**Was beim Countdown los war**
- Der Uno-Countdown lief seit dem **16.11. um 19:28** einfach weiter. Nach 90 Minuten war er durch, und
  sechs Tage später stand er natürlich auf 00:00. Uno zählt die abgelaufene Zeit weiter hoch, auch
  wenn längst Schluss ist.
- OpenRegie hat dann **„Start“ ausgegraut**. Weiter ging es nur über „↺ Zurück“, und das stand nirgends.
  Darum fühlte es sich an, als ginge gar nichts mehr.
- Mit der Szenen-Korrektur aus 1.2.1 hatte das nichts zu tun (Zeitpunkt war Zufall). Die Szenen-
  Zuordnung ist unverändert und mit echtem OBS noch einmal geprüft (20 von 20).

**Behoben / neu**
- Ist der Countdown abgelaufen, heißt der grüne Knopf **„▶ Neu starten“** und legt mit einem Klick
  wieder bei der vollen Zeit los. Darunter steht, was Sache ist.
- Countdown-Befehle gehen jetzt **schön nacheinander** zu Uno. Vorher konnte z. B. „−1 Min“ eine direkt
  danach eingetippte Zeit überholen, und bei Uno stand dann die falsche Zeit (beim Testen mit dem echten
  Uno passiert).
- **Einblenden** schaltet Inhalt und Zahlen wieder sicher mit ein. Uno meldet seit Kurzem alle Teile im
  Bauplan als „aus“, sonst hätte es nur den Kreis ohne Zahlen gegeben.
- **„Shot hinzufügen“ und „Quelle hinzufügen“ = eigenes Fenster.** Auswahl und Optionen sind genau wie
  vorher, auch Reactions. Solange es offen ist, ist das Regiepult gesperrt (nichts geht aus Versehen),
  läuft aber weiter: Live-Bild, Shot-Bilder und Countdown ticken mit. Zu geht's mit „Abbrechen“, dem
  Kreuz, Esc oder von selbst, sobald der Shot angelegt ist.
- Vorher hat „Shot hinzufügen“ rechts den Countdown verdrängt, und die Auswahl in der Bibliothek war weg.
  Auch das ist damit erledigt.

**Geprüft**
- Alle Unit-Tests: 278 von 278, viermal hintereinander. Neues OBS-Fenster-Werkzeug 3 Läufe.
- Echtes Overlays.uno („Countdown | Circles“, `werkzeuge/test_mit_echtem_uno.py`): 28 von 28. Darin
  auch Kevins Fall (abgelaufen → Neu starten) und drei Runden „schnell hintereinander“.
- Echtes Regiepult mit echtem Uno: Zeit einstellen, eintippen, bestätigen (✓ und Enter), starten,
  pausieren, weiter, zurücksetzen, ±1 Min, abgelaufen → Neu starten, Fenster auf/zu: 2 Runden, 48 von 48.
  Danach steht der Countdown wieder auf 1:30:00 und ist zurückgesetzt.
- Echtes OBS 33.0.3: neues Fenster (`werkzeuge/test_shot_fenster_mit_echtem_obs.py`, 5 Runden),
  127 von 127; Szenen-Zuordnung aus 1.2.1 weiter 20 von 20.

**Gut zu wissen**
- Beim Start am 23.11. war der Passwortspeicher des Systems gesperrt. OpenRegie fand darum kein
  Uno-Projekt (Meldung unter der Bibliothek). Wenn das passiert: das Entsperr-Fenster des Systems
  bestätigen und OpenRegie neu starten.
- Bitte einen frischen Screenshot fürs README machen und als `docs/bildschirmfoto.png` speichern.

## Build 1.2.1 – kleines Update: jede Kachel gehört fest zu ihrer Szene · 22.11.2026

**Fehlerbericht:** Zwei Szenen „Countdown“ und „Bildschirmaufnahme“ – nach dem Klick auf die
Bildschirmaufnahme war im Live-Bild nur der Countdown zu sehen.

**Was wirklich los war:** Die Kachel hat die richtige Szene geschaltet (nachgestellt mit echtem OBS).
Aber die Bildschirmaufnahme lieferte kein Bild – der Bildschirm war im Auswahlfenster des Systems nicht
(mehr) freigegeben. Und das Uno-Overlay „Countdown“ liegt automatisch in jeder Szene ganz oben.
Übrig blieb ein schwarzes Bild mit dem Countdown darauf – es sah aus wie die falsche Szene.

**Behoben / neu**
- Jede Kachel ist jetzt fest mit der **eindeutigen OBS-Kennung** ihrer Szene verknüpft (nicht mit dem
  Namen allein und nie mit der Position in der Liste). Auch Vorschaubilder und das große Live-Bild
  fragen über diese Kennung.
- Das stimmt auch nach **Umbenennen** (in OpenRegie oder in OBS), **Neuanlegen**, **Umsortieren** in OBS
  und sogar, wenn zwei Szenen ihre Namen tauschen. Die Kachel bleibt dieselbe, mit ihrem Bild.
- Wird die Szene umbenannt, die gerade live ist, zeigt OpenRegie den neuen Namen **sofort**
  (vorher erst nach ein paar Sekunden mit Fehlversuchen).
- Wenn-dann-Regeln ziehen den neuen Namen eines umbenannten Shots mit.
- **„⚠ Kein Bild“** auf der Kachel, wenn eine Aufnahme (Bildschirm, Fenster, Spiel, Kamera) nichts liefert.
  Der Hinweis verschwindet von selbst, sobald wieder ein Bild kommt.
- Beim Bearbeiten (✎) einer Bildschirmaufnahme ohne Bild: Knopf **„Bildschirm neu auswählen“** – öffnet das
  Auswahlfenster des Systems noch einmal.
- Zusätzliche Bildabfragen gibt es nur für Aufnahmen ohne Bild und nur, solange die Leiste zu sehen ist.

**Geprüft**
- Neue Unit-Tests (`tests/test_zuordnung.py`): Kevins Fall, 5 Szenen, Umbenennen, Neuanlegen, Umsortieren,
  Namen tauschen, Live-Szene umbenennen, gelöschte Szene, altes OBS ohne Kennung, Regeln – jede Prüfung
  12 Runden; mit den Shot- und OBS-Tests 12 Läufe hintereinander, je 86 von 86. Alle 272 Tests: OK.
- Echtes OBS 33.0.3 (`werkzeuge/test_zuordnung_mit_echtem_obs.py`, 5 Szenen in 5 Farben): 12 Läufe,
  je 20 von 20. Umsortieren mit der Maus lässt sich über die OBS-Schnittstelle nicht auslösen – das
  prüfen die Unit-Tests.
- Prüfwerkzeug von Build 1.2 mit echtem OBS: weiter 37 von 37.

**Gut zu wissen**
- Das Uno-Overlay liegt weiter in jedem Shot. Einstellbar, in welchen Shots es liegt, wird es in Build 1.3.
- Bitte einen frischen Screenshot fürs README machen.


**Neu: Shots (wie bei Wirecast)**
- Unter dem Live-Bild stehen alle Szenen aus OBS als große Kacheln mit kleinem Vorschaubild.
  **Ein Klick schaltet einen Shot sofort live** – der rote Rahmen zeigt, was gerade gesendet wird.
- Passen nicht alle Kacheln nebeneinander, blättert man mit ◀ ▶ (am Ende geht es vorne weiter).
- **✎ (Bearbeiten):** Danach öffnet ein Klick auf einen Shot rechts unter „AUSGEWÄHLT“ das Bearbeiten,
  statt ihn live zu schalten (gelb gestrichelter Rahmen). Dort:
  - Shot umbenennen, Shot löschen (mit „Wirklich löschen?“). Der Shot, der gerade live ist, und der
    letzte Shot lassen sich nicht löschen – der Knopf sagt warum.
  - Die Quellen im Shot als Kacheln mit Vorschaubild: anklicken, dann umbenennen oder aus dem Shot
    entfernen. „+ Quelle hinzufügen“: Kamera, Spiel, Bildschirm oder Bild.
  - „✓ Fertig“ (oder ✓ in der Leiste) beendet das Bearbeiten.
- **„+ Shot hinzufügen“** (letzte Kachel): 1. Zweck wählen – Kamera, Spiel, Reactions, Bildschirm, Bild.
  2. Das passende Layout ist gleich ausgewählt, z. B. Reactions: Video groß, deine Kamera klein rechts unten.
  Andere Layouts (links unten, rechts oben, nebeneinander, ganzes Bild) per Klick. Kleine Bildchen zeigen,
  wo die Kamera sitzt (gelb). OpenRegie legt alles im Hintergrund in OBS an – **OBS muss nie geöffnet werden.**
  - Bei Bildschirm, Spiel und Reactions fragt das System (KDE) einmal, welcher Bildschirm bzw. welches
    Fenster aufgenommen werden soll. Bei „Bild“ öffnet sich ein Fenster zum Auswählen der Datei.
  - Es gibt nur **eine** Kamera-Quelle für alle Shots (eine Kamera lässt sich nur einmal öffnen).
  - Geht beim Anlegen etwas schief, räumt OpenRegie den halben Shot wieder weg.
- Neue Quellen heißen in OBS „Kamerabild“, „Spielaufnahme“, „Reactions-Video“, „Bildschirmaufnahme“ bzw.
  „Bilddatei“ (in OBS dürfen Shot und Quelle nicht gleich heißen).
- Uno-Overlays erscheinen nicht bei den Quellen – die stehen wie bisher links in der Bibliothek.

**Neu: Wenn-dann-Fenster (Automatik)**
- Knopf **„⚡ Wenn-dann“** oben. Er zeigt auch, wie viele Regeln an sind („⚡ Wenn-dann · 2 an“).
- Links „Wenn …“, rechts „… dann“: große Auswahllisten mit Gruppen (Stream, Szenen, Overlays, Ton,
  Zeitplan). Braucht die Auswahl noch etwas (z. B. welcher Shot), erscheint darunter eine zweite Liste.
  Kein Tippen nötig.
- Auslöser: Stream startet · Stream endet · dieser Shot geht live · Startzeit im Zeitplan erreicht.
- Aktionen: Shot live schalten · Overlay einblenden/ausblenden · Ton stumm/wieder an.
- Regeln an- und ausschalten (● An / ○ Aus), bearbeiten, löschen. Gespeichert in
  `~/.local/share/openregie/automatik.json` (nur für den eigenen Benutzer lesbar).
- Schutz vor Endlosschleifen: Eine Regel löst höchstens alle 2 Sekunden aus.
- **Zeitplan** (zweiter Reiter): Tag anklicken, Uhrzeit mit −1 Std / −15 Min / +15 Min / +1 Std einstellen,
  „+ Termin eintragen“. Oben im Regiepult steht dann z. B. „Nächster Stream: Fr 19:00“.

**Sparsam mit Leistung**
- Vorschaubilder der Kacheln nur, solange die Shot-Leiste bzw. das Bearbeiten zu sehen ist: alle 5 Sekunden,
  kleines Bild (320 Pixel), immer nur eines gleichzeitig. **Zugeklappt (▾) oder minimiert: keine einzige Anfrage.**
- Die Liste der Shots wird nur nach einer Änderung in OBS neu gelesen – und nur, wenn jemand hinschaut.
- Die Automatik läuft nur, wenn mindestens eine Regel an ist. Ohne aktive Regel: keine Pegelmessung,
  kein Takt, keine Abfrage. Die Auslöser in 1.2 kosten gar nichts (OBS meldet sie ohnehin); der Zeitplan
  stellt nur einen Wecker auf den nächsten Termin.
- Das Wenn-dann-Fenster tut nichts, solange es zu ist.

**Geändert**
- Die Oberfläche spricht nur noch über die Motor-Schicht mit OBS (auch „Neu verbinden“ und „Stream beenden“
  beim Schließen). Ein Test liest den Programmtext und schlägt Alarm, wenn sich das ändert.
- Kopfleiste und Twitch-Bereich etwas flacher, damit die Shots auf Kevins Bildschirm (1903 × 971) ohne Rollen
  passen.

**Behoben (beim Test mit dem echten OBS gefunden)**
- Neue Quellen ließen sich bei manchen Typen nicht anlegen: OBS braucht den Typ mit Versionsnummer
  (z. B. „color_source_v3“). OpenRegie fragt die Typen jetzt richtig ab. Das nachgeahmte Test-OBS verhält sich
  jetzt genauso, damit so ein Fehler künftig auch ohne echtes OBS auffällt.
- Bei der Logitech BRIO wurde die Infrarot-Kamera gewählt (leeres Bild) – OBS listet sie zuerst und unter
  gleichem Namen. OpenRegie wählt jetzt die Kamera mit den meisten echten Bildformaten (bei der BRIO /dev/video0).
- Unter Wayland kennt OBS 33 keine eigene Fensteraufnahme. Spiel und Reactions nutzen darum die
  Bildschirmaufnahme – im Auswahlfenster des Systems lässt sich dort auch ein einzelnes Fenster wählen.

**Gut zu wissen**
- Die Kamera braucht nach dem Anlegen ein paar Sekunden für das erste Bild.
- OBS lässt die Kamera weiterlaufen, auch wenn gerade ein Shot ohne Kamera live ist (OBS kann das unter Linux
  nicht abschalten). Wird der letzte Shot mit Kamera gelöscht, gibt OpenRegie die Kamera ganz frei.
- Vor dem Test startete OBS gar nicht (nach einem halben System-Update fehlte eine Datei). Behoben mit
  `sudo pacman -Syu` – jetzt OBS 33.0.3.

**Geprüft**
- 258 automatische Tests, alle ohne Fehler. Die 59 neuen Tests für Shots und Wenn-dann zusätzlich
  12-mal hintereinander, jedes Mal ohne Fehler.
- Mit echtem OBS 33.0.3 (eigenes, unsichtbares Test-OBS, deine Einstellungen unberührt), 12 Läufe, jedes Mal
  37 von 37: Shots lesen und 12× live schalten, Reactions-Shot mit echter BRIO-Kamera (klein rechts unten,
  im Standbild zu sehen), Bild-Shot, 12× umbenennen, Löschen gibt Video und Kamera frei, Vorschaubilder
  stoppen beim Anhalten, „Stream startet → Shot live“ und „Stream endet → Ton stumm“ mit echtem Stream.
  Der Test aus Build 1.1 läuft weiter (26 von 26).
- **Rechenlast** (Durchschnitt über 12 Läufe, je 10 Sekunden, Anteil eines Prozessorkerns):

  | Zustand | OBS | OpenRegie | Anfragen an OBS |
  |---|---|---|---|
  | Leerlauf (Shot-Leiste zu, keine Regel) | ca. 0,7 % | 0,1–0,3 % | 0,2/s (nur On-Air-Prüfung) |
  | Shot-Leiste offen (Vorschaubilder) | ca. 0,8 % | 0,1–0,3 % | 0,7–1,0/s |
  | Regel aktiv | ca. 0,7 % | 0,1–0,3 % | 0,2/s (keine zusätzliche) |

- Aussehen mit Standbildern geprüft (Kevins Fenstergröße 1903 × 971, passt ohne Rollen).

## Build 1.1.1 – Alles passt auf den Bildschirm · 16.11.2026

**Behoben**
- Auf niedrigen Bildschirmen (z. B. 1080 Pixel mit OBS-Meldung oben) lag der grüne Start-Knopf über
  der Countdown-Zeit, man konnte sie kaum anklicken. Das Fenster brauchte über 1100 Pixel Höhe, jetzt
  höchstens 790 – auf einem 1080er-Bildschirm passt alles ohne Rollen, Knöpfe und Schrift sind gleich
  groß geblieben:
  - Die OBS-Meldung („OBS wurde unerwartet beendet …“) steht jetzt in der Mitte unter „Live-Bild“
    statt über allen drei Spalten.
  - Rechts steht „Im Stream“/„Ausgeblendet“ in einer Zeile mit „AUSGEWÄHLT“.
  - Die Überschrift „Dauer“ über −10/−1/+1/+10 Min ist weg (die Knöpfe sagen es selbst).
  - Die Texte-Fläche nimmt nur so viel Platz, wie das erste Feld braucht.
  - Ein Hinweis unter der Countdown-Zeit steht kurz an Stelle von „Bereit“/„Läuft“.
  - Nur wenn ein Bildschirm noch kleiner ist, erscheint rechts ein breiter Rollbalken – statt dass
    sich etwas überlappt. Einblenden/Ausblenden bleiben immer zu sehen.

**Geändert**
- Mit Twitch anmelden: Der Knopf ist jetzt immer zu sehen. Fehlt die Client-ID in
  `einstellungen.toml`, ist er ausgegraut und sagt, was zu tun ist (vorher war er dann unsichtbar).
  Damit haben jetzt alle 10 Knöpfe, die gesperrt werden können, einen Hinweis.
- Die öffentliche Client-ID der OpenRegie-App bei Twitch ist in `einstellungen.toml` eingetragen.

**Geprüft**
- 199 automatische Tests, alle ohne Fehler.
- Neuer Test baut Kevins Fenster nach (1903 × 971, OBS-Meldung mit „OBS starten“/„Neu verbinden“) und
  prüft: kein Rollbalken, auch nicht mit zweizeiligem Hinweis unter der Zeit. Mit dem alten Stand
  schlägt er fehl.
- Aussehen mit Standbildern geprüft.

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
