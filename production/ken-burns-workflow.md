# Ken Burns workflow — Nobi World (lokaal, geen AnimateDiff)

AnimateDiff bleek te instabiel voor een consistent personage (vervormingen). Dit is het alternatief dat veel faceless YouTube-kanalen gebruiken: **sterke stilstaande beelden + pan/zoom in de montage**, in plaats van AI-gegenereerde beweging. Geen vervormingsrisico, volledig gratis, draait vlot op je 4070.

---

## Waarom dit beter werkt voor Nobi World

- Elk beeld is een losse, scherpe SDXL-generatie met de Nobi-LoRA → personage blijft altijd correct, geen "morphing" tussen frames.
- Beweging komt uit de camera (pan/zoom/rotatie in de editor), niet uit het AI-model.
- Je hebt AnimateDiff, ControlNet of extra VRAM-zware stappen niet meer nodig — alleen SDXL + je LoRA.
- Kwaliteit oogt professioneler dan wiebelige AI-video, en dit is exact hoe veel grote faceless-kanalen (geschiedenis, feiten, kids-content) hun video's maken.

---

## 1. Wat je al hebt

- ComfyUI + SDXL-checkpoint (al geïnstalleerd)
- Nobi-LoRA (train deze gewoon zoals gepland met Kohya_ss — dat onderdeel was niet het probleem)
- Je kan **AnimateDiff-Evolved en de motion module gewoon laten staan of verwijderen** — niet meer nodig voor deze aanpak

## 2. Beelden genereren per shot

Voor elk shot uit `episodes/episode-01-het-portaal/script.md`:

1. Genereer met SDXL + Nobi-LoRA op **1024x1024** of **1344x768** (16:9-vriendelijk), prompt gebaseerd op de scene-regie.
2. Genereer bij belangrijke shots 2-3 varianten en kies de beste (geen personage-vervorming, juiste pose).
3. Exporteer als PNG, naam volgens scene: `s1-shot1.png`, `s1-shot2.png`, enz.

**Extra tip:** voor shots met beweging (Nobi rent, springt) genereer je het beeld op het "climax"-moment van de actie (bv. midden-sprong) — dat oogt dynamisch, ook stilstaand.

## 3. Pan & zoom toevoegen in de montage

**Optie A — DaVinci Resolve (gratis, aanbevolen):**
1. Sleep elk beeld op de tijdlijn, geef het de gewenste duur (5-10 sec per shot).
2. Ga naar het **Inspector-paneel** → Transform.
3. Zet een keyframe op de starttijd (bv. Zoom 100%, Position 0,0) en een keyframe op het einde (bv. Zoom 115%, lichte Position-verschuiving) → automatische pan/zoom tussen de twee.
4. Varieer richting per shot (links→rechts, in-zoom, uit-zoom) zodat het niet monotoon wordt.

**Optie B — FFmpeg (script-matig, voor bulkverwerking):**
```bash
ffmpeg -loop 1 -i s1-shot1.png -vf "zoompan=z='min(zoom+0.0015,1.15)':d=250:s=1920x1080:fps=25" -t 10 -c:v libx264 -pix_fmt yuv420p s1-shot1_panzoom.mp4
```
Dit maakt automatisch een 10-seconden zoom-in clip van een stilstaand beeld. Pas `z=` (zoomsnelheid), `d=` (aantal frames) en richting aan per shot.

**Optie C — CapCut (gratis, simpel):** heeft ingebouwde "Auto pan/zoom" per foto, minder controle maar snelst.

## 4. Waar je wél nog beweging via AI kan overwegen (optioneel, later)

Alleen voor de paar "wow"-momenten die echte beweging verdienen (portal-warp, Rokko die tot leven komt): overweeg dan alsnog een **cloud-model** (Krea/Seedance) voor die specifieke 2-3 shots — daar is consistentie/kwaliteit het probleem niet, en het is maar een klein deel van de video. De rest (90%+) blijft gratis lokaal via Ken Burns.

## 5. Rest van de pipeline blijft hetzelfde

- Voice-over: Piper/XTTS-v2 (lokaal, zie `lokale-workflow.md` stap 7)
- Muziek/SFX: gratis libraries
- Eindmontage: DaVinci Resolve — voeg voice-over, muziek, ondertitels toe over de pan/zoom-clips

---

## Verwachte tijdsinvestering aflevering 1 (met deze aanpak)

| Stap | Tijd |
|---|---|
| Nobi-LoRA trainen (eenmalig) | 30-40 min |
| ~50 shots genereren (SDXL, geen AnimateDiff) | 2-4 uur, veel sneller dan AnimateDiff-clips |
| Pan/zoom toevoegen in DaVinci | 2-3 uur |
| Voice-over + muziek + montage | 3-5 uur |

Duidelijk sneller en betrouwbaarder dan de AnimateDiff-route.
