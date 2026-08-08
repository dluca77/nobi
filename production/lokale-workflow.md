# Lokale productie-workflow — Nobi World

Volledig gratis, lokaal draaiend pipeline om scripts (zoals `episodes/episode-01-het-portaal/script.md`) om te zetten in een geanimeerde video. Vereist een eigen machine met een NVIDIA GPU (minimaal 8GB VRAM, 12GB+ aanbevolen). Op Mac (M-series) kan het meeste ook, maar trager.

> **Update:** AnimateDiff is verwijderd (te instabiel, personage-vervorming). Beweging komt nu uit pan/zoom op stilstaande SDXL-beelden — zie `ken-burns-workflow.md` voor stap 2 en 3 hieronder in detail.

---

## 1. Vereisten checken

- **GPU:** NVIDIA met CUDA (8GB VRAM = beelden ok, korte clips traag; 12-16GB = comfortabel; 24GB = vlot)
- **Windows/Linux** aanbevolen voor CUDA. Mac gaat via MPS, werkt maar trager.
- **Python 3.10/3.11**
- **~50-100GB vrije schijfruimte** (modellen zijn groot)

Check GPU:
```bash
nvidia-smi
```

---

## 2. ComfyUI installeren (de "motor")

ComfyUI is de gratis, node-based tool waarmee je Stable Diffusion + video-modellen lokaal draait.

```bash
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# NVIDIA GPU:
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

python main.py
```
Open daarna `http://127.0.0.1:8188` in je browser — dat is je werkomgeving.

---

## 3. Modellen downloaden

Zet in `ComfyUI/models/checkpoints/`:
- **SDXL** (basis beeldmodel) — https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0

Dat is alles wat je nodig hebt voor beeldgeneratie — geen motion module meer. Beweging voegen we later toe via pan/zoom in de montage (zie `ken-burns-workflow.md`).

---

## 4. Custom nodes installeren (via ComfyUI Manager)

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/ltdrdata/ComfyUI-Manager.git
```
Herstart ComfyUI, open Manager in de UI, en installeer via "Install Custom Nodes":
- **ComfyUI-VideoHelperSuite** (nuttig als je later toch nog een paar cloud-gegenereerde clips exporteert, zie `ken-burns-workflow.md` sectie 4)
- **efficiency-nodes-comfyui** (workflow-snelheid)

---

## 5. Nobi personage-consistent maken: een LoRA trainen

Zonder LoRA ziet Nobi er elke keer anders uit. Met een LoRA (klein extra bestandje dat het model "leert" hoe Nobi eruitziet) blijft hij herkenbaar.

1. Verzamel 15-30 afbeeldingen van Nobi vanuit verschillende hoeken (gebruik de character sheet die je al hebt, plus een paar Krea-generaties als extra hoeken).
2. Train lokaal met **Kohya_ss** (gratis LoRA-trainer):
   ```bash
   git clone https://github.com/bmaltais/kohya_ss.git
   cd kohya_ss
   ./setup.sh   # of setup.bat op Windows
   ```
3. Volg de GUI: dataset mappen, 15-20 minuten training op een 8GB+ GPU voor een simpel personage.
4. Zet het resultaat (`nobi.safetensors`) in `ComfyUI/models/loras/`.
5. In je prompt gebruik je dan: `<lora:nobi:0.8> Nobi, yellow block head, blue hoodie, ...`

Dit is de belangrijkste stap voor kwaliteit — zonder LoRA is consistentie het grootste probleem.

---

## 6. Workflow per shot (herhaal per scene uit het script)

1. **Beeld genereren** in ComfyUI met SDXL + Nobi-LoRA, prompt gebaseerd op de scene-regie in het script (bijv. Scene 1, Shot 2: "close-up Nobi verbaasd gezicht"). Exporteer als PNG, bestandsnaam volgens scene (`s1-shot2.png`).
2. **Pan/zoom toevoegen** in DaVinci Resolve of via FFmpeg — zie `ken-burns-workflow.md` sectie 3 voor de volledige uitleg.
3. Herhaal voor alle ±40-60 shots die een script van 10 minuten nodig heeft (reken op 1 beeld per 8-12 seconden eindresultaat).

**Tip:** genereer bewegende shots (rennen, springen, portal-warp) op het climax-moment van de actie — dat oogt dynamisch, ook als stilstaand beeld. Zie `ken-burns-workflow.md` sectie 4 voor de paar shots waar je alsnog echte AI-beweging (cloud) wil overwegen.

---

## 7. Voice-over lokaal genereren

**Piper TTS** (snel, gratis, goede kwaliteit, draait zelfs zonder GPU):
```bash
pip install piper-tts
# download een Nederlandse stem, bv. nl_NL-mls-medium
piper --model nl_NL-mls-medium.onnx --output_file scene1.wav < scene1_tekst.txt
```
Kopieer de voice-over tekst per scene direct uit `script.md`.

Voor een unieke "Nobi-stem" kun je met **XTTS-v2** (Coqui, lokaal, voice cloning) een eigen stem klonen op basis van een paar minuten audio.

---

## 8. Muziek & SFX

- Gratis: YouTube Audio Library, Pixabay Music, Freesound.org (let op licenties bij commercieel gebruik)
- Of lokaal genereren met **MusicGen** (Meta, draait via ComfyUI of standalone, gratis)

---

## 9. Monteren tot eindvideo

Gebruik **DaVinci Resolve** (gratis, professioneel):
1. Importeer alle shot-clips in scene-volgorde.
2. Leg voice-over per scene op de audio-track, sync met de clips.
3. Voeg muziek + SFX toe op aparte tracks, mix volumes.
4. Voeg ondertitels toe (belangrijk voor kids-kanalen, ook voor bereik).
5. Exporteer als 1080p/4K mp4.

Of automatiseer het stitchen met **FFmpeg** als je liever scriptmatig werkt:
```bash
ffmpeg -f concat -safe 0 -i shotlist.txt -c copy episode-01-raw.mp4
```

---

## 10. Realistische tijdsinschatting (eerste keer)

| Stap | Tijd |
|---|---|
| ComfyUI + modellen installeren | 2-4 uur |
| LoRA trainen | 1-2 uur (grotendeels wachttijd) |
| Beelden genereren (10 min episode, ~50 shots) + pan/zoom in montage | 1-2 dagen (afhankelijk van GPU, sneller dan AnimateDiff-clips) |
| Voice-over + muziek | 2-4 uur |
| Monteren | 3-6 uur |

Na de eerste aflevering ga je sneller omdat de LoRA en workflow-templates al klaarstaan.

---

## Alternatief: hybride aanpak

Overweeg dit te combineren: gebruik lokale ComfyUI voor de meeste shots (gratis), en val alleen terug op Krea (cloud, betaald) voor de paar shots waar je topkwaliteit nodig hebt (bv. de titelcard of thumbnail). Dat bespaart credits en houdt kwaliteit hoog waar het telt.
