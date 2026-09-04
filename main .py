import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from io import BytesIO

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, EmailStr
from google import genai
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

# Configuration des identifiants
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# Initialisation de l'application FastAPI
app = FastAPI(title="Chariow PDF E-Book Generator")

# Initialisation du client Google GenAI
if GEMINI_API_KEY:
    ai_client = genai.Client(api_key=GEMINI_API_KEY)
else:
    ai_client = None

# Modèle de requête reçu lors d'une commande
class EbookRequest(BaseModel):
    topic: str
    recipient_email: EmailStr

# --- FONCTION 1 : Génération du contenu via Gemini ---
def generate_ebook_text(topic: str) -> str:
    if not ai_client:
        raise ValueError("GEMINI_API_KEY non configurée dans les variables d'environnement.")
    
    prompt = f"""
    Rédige un petit e-book complet, instructif et bien structuré sur le sujet suivant : '{topic}'.
    Inclus une introduction captivante, 3 chapitres détaillés et une conclusion pratique.
    Le ton doit être professionnel, clair et engageant pour un guide numérique.
    """
    
    response = ai_client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )
    return response.text

# --- FONCTION 2 : Création du fichier PDF en mémoire ---
def create_pdf_in_memory(text_content: str, title: str) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    
    styles = getSampleStyleSheet()
    normal_style = styles['Normal']
    normal_style.fontSize = 11
    normal_style.leading = 15
    
    title_style = ParagraphStyle(
        'EbookTitle',
        parent=styles['Heading1'],
        fontSize=20,
        leading=24,
        spaceAfter=20
    )

    story = []
    story.append(Paragraph(f"<b>Guide Complet : {title.capitalized()}</b>", title_style))
    story.append(Spacer(1, 15))

    paragraphs = text_content.split("\n")
    for para in paragraphs:
        cleaned_para = para.strip()
        if cleaned_para:
            story.append(Paragraph(cleaned_para, normal_style))
            story.append(Spacer(1, 8))

    doc.build(story)
    buffer.seek(0)
    return buffer

# --- FONCTION 3 : Envoi de l'e-mail avec le PDF joint ---
def send_email_with_pdf(recipient_email: str, pdf_buffer: BytesIO, topic: str):
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        raise ValueError("Identifiants SMTP manquants dans les variables d'environnement.")

    msg = MIMEMultipart()
    msg['From'] = SMTP_EMAIL
    msg['To'] = recipient_email
    msg['Subject'] = f"Votre E-Book est prêt : {topic.capitalize()}"

    body = f"Bonjour,\n\nMerci pour votre commande ! Veuillez trouver en pièce jointe votre e-book au format PDF sur le thème : '{topic}'.\n\nBonne lecture !"
    msg.attach(MIMEText(body, 'plain'))

    part = MIMEBase('application', 'octet-stream')
    part.set_payload(pdf_buffer.read())
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename="ebook_{topic.lower().replace(" ", "_")}.pdf"')
    msg.attach(part)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.send_message(msg)

# Pipeline exécuté en arrière-plan
def process_ebook_order(topic: str, recipient_email: str):
    try:
        content = generate_ebook_text(topic)
        pdf_buffer = create_pdf_in_memory(content, topic)
        send_email_with_pdf(recipient_email, pdf_buffer, topic)
    except Exception as e:
        print(f"Erreur lors du traitement de la commande : {e}")

# --- ROUTES FASTAPI ---

@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <html>
        <head>
            <title>Chariow PDF E-Book Generator</title>
            <style>
                body { font-family: sans-serif; text-align: center; padding-top: 50px; background-color: #f4f4f9; }
                .card { background: white; padding: 30px; display: inline-block; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
                h1 { color: #333; }
                p { color: #666; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Service de Génération d'E-Book d'IA</h1>
                <p>Le serveur backend est <strong>en ligne et fonctionnel (Live)</strong>.</p>
                <p>Prêt à recevoir les Webhooks d'achat pour envoyer des PDF automatisés.</p>
            </div>
        </body>
    </html>
    """

@app.post("/generate-ebook")
def generate_ebook_endpoint(request: EbookRequest, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_ebook_order, request.topic, request.recipient_email)
    return {
        "status": "success",
        "message": f"La génération de l'e-book sur '{request.topic}' est lancée. Il sera envoyé à {request.recipient_email} dès qu'il sera prêt."
    }
