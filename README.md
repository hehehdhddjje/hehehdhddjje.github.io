# yt-dlp Enhanced Mod

Site public : https://hehehdhddjje.github.io/

## Important

GitHub Pages héberge uniquement l’interface statique. Il ne peut pas exécuter Python, FastAPI, FFmpeg ou yt-dlp. Les téléchargements sont donc exécutés par le serveur local inclus dans ce dépôt.

## Lancer le serveur local

Sous Ubuntu/Debian :

```bash
sudo apt update
sudo apt install -y python3 python3-venv ffmpeg
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Ensuite, ouvre https://hehehdhddjje.github.io/ ou http://127.0.0.1:8000/. Les fichiers téléchargés sont enregistrés dans `downloads/`.

## Structure

- `index.html` : interface publiée sur GitHub Pages ;
- `app.py` : serveur FastAPI local ;
- `templates/index.html` : interface complète du serveur local ;
- `requirements.txt` : dépendances Python ;
- `downloads/` : fichiers téléchargés localement.
