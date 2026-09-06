import os
import io
import base64

from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel, EmailStr
import google.generativeai as genai
import resend
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Initialisation de FastAPI
app = FastAPI(
    title="Chariow PDF E-Book Generator",
    description="Service backend pour générer des e-books PDF via Gemini et les envoyer via Resend.",
    version="1.0.0"
)

# Configuration de la clé API Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# Configuration de la clé API Resend
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
if RESEND_API_KEY:
    resend.api_key = RESEND_API_KEY

# Modèle de données pour la requête
class EBookRequest(BaseModel):
    topic: str
    recipient_email: EmailStr

# --- FONCTION 1 : Génération du contenu via Gemini ---
def generate_ebook_text(topic: str) -> str:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY non configurée dans les variables d'environnement.")
    
    prompt = f"""
    Rédige un e-book complet, synthétique, bien structuré et captivant sur le sujet suivant : '{topic}'.
    Inclus une introduction percutante, 3 chapitres détaillés et une conclusion pratique.
    Le ton doit être professionnel, clair et engageant pour un guide numérique.
    """
    
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(prompt)
    return response.text

# --- FONCTION 2 : Création du PDF avec ReportLab ---
def build_pdf(text: str) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'EbookTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        textColor='#1A202C',
        spaceAfter=20
    )
    body_style = ParagraphStyle(
        'EbookBody',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
        textColor='#2D3748',
        spaceAfter=10
    )
    
    story = []
    lines = text.split('\n')
    
    for line in lines:
        line_str = line.strip()
        if not line_str:
            story.append(Spacer(1, 8))
            continue
        
        if line_str.startswith('#') or (line_str.isupper() and len(line_str) < 50):
            clean_title = line_str.lstrip('#').strip()
            story.append(Paragraph(clean_title, title_style))
        else:
            story.append(Paragraph(line_str, body_style))
            
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- FONCTION 3 : Envoi d'e-mail via l'API Resend ---
def send_email_with_pdf(recipient_email: str, pdf_bytes: bytes, topic: str):
    if not RESEND_API_KEY:
        raise ValueError("RESEND_API_KEY non configurée dans les variables d'environnement.")
        
    filename = f"ebook_{topic.replace(' ', '_').lower()[:20]}.pdf"
    
    # Encodage du fichier PDF en base64 pour l'API Resend
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
    
    params = {
        "from": "onboarding@resend.dev",  # Adresse de test officielle fournie par Resend
        "to": recipient_email,
        "subject": f"Votre E-Book gratuit : {topic}",
        "html": f"<p>Bonjour,</p><p>Veuillez trouver ci-joint votre e-book personnalisé sur <strong>'{topic}'</strong>.</p><p>Bonne lecture !</p>",
        "attachments": [
            {
                "filename": filename,
                "content": pdf_base64,
            }
        ]
    }
    
    response = resend.Emails.send(params)
    print(f"[RESEND RESPONSE] {response}")

# --- TÂCHE EN ARRIÈRE-PLAN ---
def process_ebook_generation(topic: str, recipient_email: str):
    try:
        text = generate_ebook_text(topic)
        pdf_bytes = build_pdf(text)
        send_email_with_pdf(recipient_email, pdf_bytes, topic)
        print(f"[SUCCÈS] E-book sur '{topic}' envoyé avec succès via Resend à {recipient_email}")
    except Exception as e:
        print(f"[ERREUR] Échec du traitement : {e}")

# --- ENDPOINTS ---
@app.get("/", tags=["Home"])
def read_root():
    return {
        "service": "Service de Génération d'E-Book d'IA (Resend Emailing)",
        "status": "Live",
        "message": "Prêt à recevoir les requêtes."
    }

@app.post("/generate-ebook", tags=["E-Book Generator"])
def generate_ebook(request: EBookRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_ebook_generation, request.topic, request.recipient_email)
    return {
        "status": "success",
        "message": f"La génération de l'e-book sur '{request.topic}' est lancée. Il sera envoyé à {request.recipient_email} sous peu."
    }
