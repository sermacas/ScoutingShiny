import pandas as pd
from shiny import App, ui, render, reactive, run_app
import nest_asyncio
import asyncio
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import time
import re
from fpdf import FPDF
from datetime import datetime
import os
import tempfile
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, RegularPolygon
from matplotlib.path import Path
from matplotlib.projections.polar import PolarAxes
from matplotlib.projections import register_projection
from matplotlib.spines import Spine
from matplotlib.transforms import Affine2D
from math import pi
import numpy as np
import seaborn as sns
import numpy as np
import plotly.graph_objects as go
from shinywidgets import output_widget, render_widget,render_plotly
from shiny.ui import div, h3, hr, br
import plotly.express as px
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE
from sklearn.metrics.pairwise import cosine_similarity
import plotly.express as px
import nest_asyncio 
import gspread
from google.oauth2.service_account import Credentials
import json

# Obtener SCOPES como lista desde variable de entorno (separados por coma)
SCOPES = os.getenv("SCOPES")
GOOGLE_API_KEY =  os.getenv("GOOGLE_API_KEY")
GOOGLE_CX =  os.getenv("GOOGLE_CX")
YOUTUBE_API_KEY =  os.getenv("YOUTUBE_API_KEY")
# Obtener el JSON desde variable de entorno y convertirlo a dict
service_account_info = json.loads(os.getenv("SERVICE_ACCOUNT_JSON"))

# Crear las credenciales desde el dict
credentials = Credentials.from_service_account_info(
    service_account_info,
    scopes=SCOPES
)

# Autorización y conexión con gspread
gc = gspread.authorize(credentials)




# Ruta al archivo JSON con credenciales de la cuenta de servicio
SERVICE_ACCOUNT_FILE = "/Users/sergiomarincastro/Big Data Deportivo/Proyectos/TFG/mi_archivo_credenciales.json"

spreadsheet_id = "13v-7cMMUIoSqEJL-QUfVAlFx2AgFqaG7DLlEtyzgDbs"

gid_hoja1 = "1269319670"
gid_hoja2 = "654483830"
gid_hoja3 = "40604871"


def url_csv(spreadsheet_id, gid):
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/export?format=csv&gid={gid}"

url_hoja1 = url_csv(spreadsheet_id, gid_hoja1)
url_hoja2 = url_csv(spreadsheet_id, gid_hoja2)
url_hoja3 = url_csv(spreadsheet_id, gid_hoja3)

df = pd.read_csv(url_hoja1, low_memory=False)
df2 = pd.read_csv(url_hoja2,low_memory=False)
df3 = pd.read_csv(url_hoja3,low_memory=False)

def infer_and_clean_numeric(df):
    for col in df.columns:
        # Skip if already numeric
        if pd.api.types.is_numeric_dtype(df[col]):
            continue
            
        # Convert to string and clean
        sample = df[col].dropna().astype(str)
        
        # Replace commas with dots and remove any whitespace
        sample = sample.str.replace(',', '.').str.strip()
        
        # Check what percentage can be converted to numeric
        numeric_ratio = sample.apply(lambda x: x.replace('.', '', 1).lstrip('-').isdigit()).mean()
        
        if numeric_ratio > 0.8:
            try:
                # First try converting directly
                df[col] = pd.to_numeric(sample, errors='coerce')
                
                # If all values became NA, try replacing commas first
                if df[col].isna().all():
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
            except:
                df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '.'), errors='coerce')
    
    return df


df = infer_and_clean_numeric(df)
df2 = infer_and_clean_numeric(df2)
df3 = infer_and_clean_numeric(df3)

columns = [
    "season", 
    "playerName", 
    "squadName", 
    "competitionName", 
    "birthdate", 
    "birthplace", 
    "leg", 
    "positions", 
    "playDuration", 
    "IMPECT_SCORE_PACKING", 
    "IMPECT_SCORE_WITHOUT_GOALS_PACKING", 
    "OFFENSIVE_IMPECT_SCORE_PACKING", 
    "DEFENSIVE_IMPECT_SCORE_PACKING"]

df = df[[col for col in columns if col in df.columns]]

# Asumiendo que ya tienes un DataFrame llamado 'df'
df['playDuration'] = (df['playDuration'] * 4530) / 231093.25

# Opcional: Redondear a 3 decimales (como en el ejemplo)
df['playDuration'] = df['playDuration'].round(3)

REQUIRED_FIELDS = {
    "Nombre": "nuevo_nombre",
    "Competición": "nuevo_competencia",
    "Equipo": "nuevo_equipo",
    "Pierna hábil": "nuevo_leg",
    "Fecha de nacimiento": "nuevo_birthdate"
}
# ======================
# FUNCIONES DE TRANSFERMARKT
# ======================
def sync_get_detailed_transfermarkt_results(query, max_retries=3):
    """Versión síncrona de la función de búsqueda en Transfermarkt"""
    base_url = "https://www.transfermarkt.es"
    search_url = f"{base_url}/schnellsuche/ergebnis/schnellsuche?query={quote(query)}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept-Language': 'es-ES,es;q=0.9',
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(search_url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')
            
            results = []
            table = soup.find('table', class_='items')
            
            if table:
                rows = table.find_all('tr', class_=['odd', 'even'])
                for row in rows:
                    img_tag = row.find('img', class_='bilderrahmen-fixed')
                    player_image = img_tag['src'] if img_tag else "N/A"
                    
                    name_tag = row.find('a', title=True, href=lambda x: '/profil/spieler/' in x)
                    player_name = name_tag.get_text(strip=True) if name_tag else "N/A"
                    player_link = base_url + name_tag['href'] if name_tag else "N/A"
                    
                    club_tag = row.find('a', title=True, href=lambda x: '/startseite/verein/' in x)
                    club_name = club_tag.get_text(strip=True) if club_tag else "N/A"
                    club_link = base_url + club_tag['href'] if club_tag else "N/A"
                    club_logo = row.find('img', class_='tiny_wappen')['src'] if row.find('img', class_='tiny_wappen') else "N/A"
                    
                    position = row.find_all('td', class_='zentriert')[0].get_text(strip=True) if row.find_all('td', class_='zentriert') else "N/A"
                    age = row.find_all('td', class_='zentriert')[2].get_text(strip=True) if len(row.find_all('td', class_='zentriert')) > 1 else "N/A"
                    flags = [img['title'] for img in row.find_all('img', class_='flaggenrahmen')] if row.find_all('img', class_='flaggenrahmen') else ["N/A"]
                    market_value = row.find('td', class_='rechts hauptlink').get_text(strip=True) if row.find('td', class_='rechts hauptlink') else "N/A"
                    agent = row.find('span').get_text(strip=True) if row.find('span') else "N/A"
                    
                    results.append({
                        'Imagen': player_image,
                        'Nombre': player_name,
                        'Enlace': player_link,
                        'Posición': position,
                        'Club': club_name,
                        'Escudo Club': club_logo,
                        'Enlace Club': club_link,
                        'Edad': age,
                        'Nacionalidad': flags,
                        'Valor de mercado': market_value,
                        'Agente': agent
                    })
            
            return results if results else [{"Error": "No se encontraron resultados."}]
        
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                return [{"Error": f"Error de conexión después de {max_retries} intentos: {e}"}]
            print(f"Intento {attempt + 1} fallido. Reintentando en 5 segundos...")
            time.sleep(5)
        except Exception as e:
            return [{"Error": f"Error inesperado: {e}"}]
        
def sync_scrape_player_info(url):
    """Versión síncrona del scraper de detalles de jugador"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        player_data = {}
        info_table = soup.find('div', class_='info-table')
        
        if info_table:
            # Extraer datos básicos
            nombre_label = info_table.find('span', string='Nombre en país de origen:')
            nombre_label2 = info_table.find('span', string='Nombre completo:')
            if nombre_label:
                player_data['nombre'] = nombre_label.find_next('span', class_='info-table__content--bold').get_text(strip=True)
            elif nombre_label2:
                player_data['nombre'] = nombre_label2.find_next('span', class_='info-table__content--bold').get_text(strip=True)
            
            fecha_label = info_table.find('span', string='F. Nacim./Edad:')
            if fecha_label:
                fecha_span = fecha_label.find_next('span', class_='info-table__content--bold')
                player_data['fecha_nacimiento'] = fecha_span.get_text(strip=True).split('(')[0].strip()
                player_data['edad'] = fecha_span.get_text(strip=True).split('(')[1].replace(')', '').strip()
            
            lugar_label = info_table.find('span', string='Lugar de nac.:')
            if lugar_label:
                lugar_span = lugar_label.find_next('span', class_='info-table__content--bold')
                player_data['lugar_nacimiento'] = lugar_span.get_text(strip=True).split('  ')[0]
            
            altura_label = info_table.find('span', string='Altura:')
            if altura_label:
                player_data['altura'] = altura_label.find_next('span', class_='info-table__content--bold').get_text(strip=True)
            
            nacionalidad_label = info_table.find('span', string='Nacionalidad:')
            if nacionalidad_label:
                nacionalidad_span = nacionalidad_label.find_next('span', class_='info-table__content--bold')
                # Extraer el texto y separar las nacionalidades
                nacionalidad_text = nacionalidad_span.get_text(strip=True)
                # Separar cuando encuentre una letra mayúscula seguida de minúsculas (regex)
                nacionalidades = re.findall('[A-Z][^A-Z]*', nacionalidad_text)
                player_data['nacionalidad'] = ', '.join(nacionalidades)
            
            posicion_label = info_table.find('span', string='Posición:')
            if posicion_label:
                player_data['posicion'] = posicion_label.find_next('span', class_='info-table__content--bold').get_text(strip=True)
            
            pie_label = info_table.find('span', string='Pie:')
            if pie_label:
                player_data['pie'] = pie_label.find_next('span', class_='info-table__content--bold').get_text(strip=True)
            
            agente_label = info_table.find('span', string='Agente:')
            if agente_label:
                agente_span = agente_label.find_next('span', class_='info-table__content--bold')
                player_data['agente'] = agente_span.get_text(strip=True)

            
            # Ajuste del scraping para encontrar el 'Club actual'
            club_label = info_table.find('span', string=lambda text: 'Club actual' in text if text else False)
            if club_label:
                club_span = club_label.find_next('span', class_='info-table__content--bold')
                if club_span:
                    player_data['club_actual'] = club_span.get_text(strip=True)
                else:
                    print("No se encontró el club en el siguiente span.")
            else:
                print("No se encontró el label 'Club actual' en la página.")
                
            fichado_label = info_table.find('span', string='Fichado:')
            if fichado_label:
                player_data['fichado'] = fichado_label.find_next('span', class_='info-table__content--bold').get_text(strip=True)
            
            contrato_label = info_table.find('span', string='Contrato hasta:')
            if contrato_label:
                player_data['contrato_hasta'] = contrato_label.find_next('span', class_='info-table__content--bold').get_text(strip=True)
            
            renovacion_label = info_table.find('span', string='Última renovación:')
            if renovacion_label:
                player_data['contrato_hasta'] = renovacion_label.find_next('span', class_='info-table__content--bold').get_text(strip=True)
            
            market_value_div = soup.find('div', class_='data-header__box--small')
            if market_value_div:
                market_value_wrapper = market_value_div.find('a', class_='data-header__market-value-wrapper')
                if market_value_wrapper:
                    value_text = market_value_wrapper.get_text(strip=True).split('€')[0].strip()
                    player_data['valor_mercado'] = value_text
        
        # Scrapear información de lesiones
        base_url = '/'.join(url.split('/')[:3])
        injuries_url = urljoin(base_url, f"/{url.split('/')[3]}/verletzungen/spieler/{url.split('/')[-1]}")
        
        try:
            injuries_response = requests.get(injuries_url, headers=headers)
            injuries_response.raise_for_status()
            injuries_soup = BeautifulSoup(injuries_response.text, 'html.parser')
            
            injuries_table = injuries_soup.find('table', class_='items')
            player_data['lesiones'] = []
            
            if injuries_table:
                rows = injuries_table.find('tbody').find_all('tr')
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 6:
                        lesion = {
                            'Temporada': cols[0].get_text(strip=True),
                            'Tipo': cols[1].get_text(strip=True),
                            'Fecha_Inicio': cols[2].get_text(strip=True),
                            'Fecha_Fin': cols[3].get_text(strip=True),
                            'Dias_Lesionado': cols[4].get_text(strip=True),
                            'Partidos_Perdidos': cols[5].get_text(strip=True)
                        }
                        player_data['lesiones'].append(lesion)
        except Exception as e:
            player_data['error_lesiones'] = f"No se pudo obtener el historial de lesiones: {str(e)}"
        
        return player_data
    
    except Exception as e:
        return {"Error": f"Error al obtener información del jugador: {str(e)}"}


def get_player_achievements(player_id):
    """Obtiene los logros del jugador desde Transfermarkt"""
    url = f'https://www.transfermarkt.es/jugador/erfolge/spieler/{player_id}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'es-ES,es;q=0.9'
    }

    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Respuesta no exitosa: {response.status_code}")
            return pd.DataFrame()

        soup = BeautifulSoup(response.content, 'html.parser')
        achievement_sections = soup.find_all('div', class_='box')

        data = []

        for section in achievement_sections:
            category_title = section.find('h2')
            if not category_title:
                continue
            current_category = category_title.get_text(strip=True)

            rows = section.find_all('tr')
            for row in rows:
                # Actualizar categoría si la fila es una subcategoría (como '1x Descendido...')
                if 'bg_Sturm' in row.get('class', []):
                    current_category = row.get_text(strip=True)
                    continue

                cols = row.find_all('td')
                if len(cols) >= 2:
                    season = cols[0].get_text(strip=True)
                    detail_td = cols[2]

                    detail_text = detail_td.get_text(strip=True)
                    img = detail_td.find('img')
                    if img and img.has_attr('title'):
                        detail_text = img['title']

                    data.append({
                        'Categoría': current_category,
                        'Temporada': season,
                        'Club': detail_text
                    })

        return pd.DataFrame(data).drop_duplicates()


    except Exception as e:
        print(f"Error obteniendo logros del jugador: {str(e)}")
        return pd.DataFrame()
    
def get_player_stats(player_id):
    """Obtiene las estadísticas históricas del jugador desde Transfermarkt"""
    url = f'https://www.transfermarkt.es/jugador/leistungsdatendetails/spieler/{player_id}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'es-ES,es;q=0.9'
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.find('table', {'class': 'items'})
        
        if not table:
            print("Tabla no encontrada")
            return None

        column_headers = [
            'Temporada',
            'Competición',
            'Club',
            'Alineaciones',
            'Goles',
            'Asistencias',
            'Tarjetas',
            'Minutos'
        ]

        data = []
        tbody = table.find('tbody')
        
        for row in tbody.find_all('tr'):
            cols = row.find_all(['td', 'th'])
            
            temporada = cols[0].get_text(strip=True)
            competicion = extract_competition(cols[2])
            club = extract_club(cols[3])
            alineaciones = cols[4].get_text(strip=True)
            goles = cols[5].get_text(strip=True)
            asistencias = cols[6].get_text(strip=True)
            tarjetas = cols[7].get_text(strip=True)
            minutos = cols[8].get_text(strip=True).replace("'", "").replace(".", "")
            
            data.append([
                temporada,
                competicion,
                club,
                alineaciones,
                goles,
                asistencias,
                tarjetas,
                minutos
            ])

        df = pd.DataFrame(data, columns=column_headers)
        df = df.replace('-', '0')
        df['Minutos'] = pd.to_numeric(df['Minutos'], errors='coerce').fillna(0).astype(int)
        df['Alineaciones'] = pd.to_numeric(df['Alineaciones'], errors='coerce').fillna(0).astype(int)
        df['Goles'] = pd.to_numeric(df['Goles'], errors='coerce').fillna(0).astype(int)
        df['Asistencias'] = pd.to_numeric(df['Asistencias'], errors='coerce').fillna(0).astype(int)
        
        return df

    except Exception as e:
        print(f"Error obteniendo estadísticas del jugador: {str(e)}")
        return None

def extract_competition(td):
    """Extrae el nombre de la competición del td"""
    a_tag = td.find('a')
    if a_tag:
        return a_tag.get('title', a_tag.get_text(strip=True))
    return td.get_text(strip=True)

def extract_club(td):
    """Extrae el nombre del club del td"""
    a_tag = td.find('a')
    if a_tag:
        return a_tag.get('title', a_tag.get_text(strip=True))
    return td.get_text(strip=True)

def google_image_search(player_name, team_name=None, api_key=GOOGLE_API_KEY, cx=GOOGLE_CX):
    """Busca la primera imagen relevante de un jugador usando la API de Google Custom Search."""
    try:
        query = f"{player_name} {team_name} futbolista".strip()
        url = (
            "https://www.googleapis.com/customsearch/v1?"
            f"q={quote(query)}&searchType=image&key={api_key}&cx={cx}&num=3&imgSize=large"
        )
        response = requests.get(url)
        response.raise_for_status()
        items = response.json().get('items', [])

        return items[0]['link'] if items else None
    except Exception as e:
        print(f"Error en la búsqueda de imágenes: {e}")
        return None

def google_club_image_search(club_name, api_key=GOOGLE_API_KEY, cx=GOOGLE_CX):
    """Busca la primera imagen relevante de un club de fútbol usando la API de Google Custom Search."""
    try:
        query = f"{club_name} escudo png"
        url = (
            "https://www.googleapis.com/customsearch/v1?"
            f"q={quote(query)}&searchType=image&key={api_key}&cx={cx}&num=3&imgSize=medium"
        )
        response = requests.get(url)
        response.raise_for_status()
        items = response.json().get('items', [])
        
        # Si no hay resultados, intenta una búsqueda más simple
        if not items:
            query = f"{club_name} logo"
            url = (
                "https://www.googleapis.com/customsearch/v1?"
                f"q={quote(query)}&searchType=image&key={api_key}&cx={cx}&num=3&imgSize=medium"
            )
            response = requests.get(url)
            response.raise_for_status()
            items = response.json().get('items', [])

        return items[0]['link'] if items else None
    except Exception as e:
        print(f"Error en la búsqueda de imágenes del club: {e}")
        return None
    
 
def google_coach_image_search(coach_name, team_name=None, api_key=GOOGLE_API_KEY, cx=GOOGLE_CX):
    """Busca la primera imagen relevante de un jugador usando la API de Google Custom Search."""
    try:
        query = f"{coach_name} entrenador".strip()
        url = (
            "https://www.googleapis.com/customsearch/v1?"
            f"q={quote(query)}&searchType=image&key={api_key}&cx={cx}&num=3&imgSize=large"
        )
        response = requests.get(url)
        response.raise_for_status()
        items = response.json().get('items', [])

        return items[0]['link'] if items else None
    except Exception as e:
        print(f"Error en la búsqueda de imágenes: {e}")
        return None
      
def buscar_noticias_deportivas(jugador, club="", num_noticias=6):
    """Busca noticias deportivas relevantes excluyendo Wikipedia y redes sociales"""
    try:
        # Términos a excluir
        exclude_sites = "-site:wikipedia.org -site:twitter.com -site:instagram.com -site:facebook.com"
        query = f"{jugador} {club} fútbol {exclude_sites} -mercado -traspaso -rumor -venta -compra"
        
        url = f"https://www.googleapis.com/customsearch/v1?q={query}&key={GOOGLE_API_KEY}&cx={GOOGLE_CX}&num={num_noticias+2}"  # Buscamos extras por si hay que filtrar
        
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        if 'items' not in data:
            return None
            
        # Filtrar resultados no deseados
        noticias_filtradas = []
        dominios_permitidos = ['.com', '.es', '.net', '.org']  # Excluimos otros TLDs menos comunes
        palabras_excluir = ['perfil', 'biografía', 'estadísticas', 'instagram', 'twitter']
        
        for item in data['items']:
            link = item.get('link', '').lower()
            titulo = item.get('title', '').lower()
            
            # Verificar si es una noticia válida
            es_valida = all([
                any(dominio in link for dominio in dominios_permitidos),
                not any(palabra in titulo or palabra in link for palabra in palabras_excluir),
                not link.split('/')[2].startswith(('www.wiki', 'es.wiki'))  # Excluir cualquier wiki
            ])
            
            if es_valida and len(noticias_filtradas) < num_noticias:
                noticias_filtradas.append({
                    'titulo': item.get('title', 'Sin título'),
                    'fuente': item.get('displayLink', 'Fuente desconocida').replace('www.', ''),
                    'fecha': item.get('snippet', '')[:150] + '...',
                    'enlace': item.get('link', '#')
                })
        
        return noticias_filtradas if noticias_filtradas else None
        
    except Exception as e:
        print(f"Error en la búsqueda: {str(e)}")
        return None
    
def buscar_highlights_youtube(jugador, club="", max_results=3):
    """Busca videos de highlights en YouTube"""
    try:
        query = f"{jugador} {club} highlights 2023 goles asistencias"
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&maxResults={max_results}&q={quote(query)}&key={YOUTUBE_API_KEY}&type=video&order=relevance"
        
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        videos = []
        for item in data.get('items', []):
            videos.append({
                'id': item['id']['videoId'],
                'titulo': item['snippet']['title'],
                'canal': item['snippet']['channelTitle'],
                'fecha': item['snippet']['publishedAt'][:10],
                'thumbnail': item['snippet']['thumbnails']['high']['url']
            })
        return videos if videos else None
        
    except Exception as e:
        print(f"Error en búsqueda de YouTube: {str(e)}")
        return None
    
NATIONALITY_TO_CODE = {
    # Europa
    'Albania': 'al',
    'Alemania': 'de',
    'Austria': 'at',
    'Bélgica': 'be',
    'Croacia': 'hr',
    'Dinamarca': 'dk',
    'Escocia': 'gb-sct',
    'España': 'es',
    'Finlandia': 'fi',
    'Francia': 'fr',
    'Gales': 'gb-wls',
    'Grecia': 'gr',
    'Holanda': 'nl',
    'Inglaterra': 'gb-eng',
    'Irlanda': 'ie',
    'Italia': 'it',
    'Noruega': 'no',
    'Polonia': 'pl',
    'Portugal': 'pt',
    'República Checa': 'cz',
    'Rusia': 'ru',
    'Serbia': 'rs',
    'Suecia': 'se',
    'Suiza': 'ch',
    'Turquía': 'tr',
    'Ucrania': 'ua',

    # América del Norte y Central
    'Canadá': 'ca',
    'Estados Unidos': 'us',
    'México': 'mx',

    # Sudamérica
    'Argentina': 'ar',
    'Bolivia': 'bo',
    'Brasil': 'br',
    'Chile': 'cl',
    'Colombia': 'co',
    'Ecuador': 'ec',
    'Paraguay': 'py',
    'Perú': 'pe',
    'Uruguay': 'uy',
    'Venezuela': 've',

    # África
    'Argelia': 'dz',
    'Angola': 'ao',
    'Camerún': 'cm',
    'Cabo Verde': 'cv',
    'Congo': 'cg',
    'Costa de Marfil': 'ci',
    'Egipto': 'eg',
    'Ghana': 'gh',
    'Guinea': 'gn',
    'Mali': 'ml',
    'Marruecos': 'ma',
    'Nigeria': 'ng',
    'Senegal': 'sn',
    'Sudáfrica': 'za',
    'Túnez': 'tn',

    # Asia / Oceanía
    'Corea del Sur': 'kr',
    'Japón': 'jp',
    'Irán': 'ir',
    'Arabia Saudita': 'sa',
    'Australia': 'au'
}


def get_country_flags(nationalities_str):
    """Procesa una cadena de nacionalidades separadas por comas y devuelve listado de banderas"""
    if not nationalities_str:
        return []
    
    # Separar y limpiar nacionalidades
    nationalities = [n.strip() for n in nationalities_str.split(',')]
    flags = []
    
    for nation in nationalities:
        normalized = nation.lower().capitalize()
        if code := NATIONALITY_TO_CODE.get(normalized):
            flags.append({
                'name': nation,
                'image_url': f"https://flagcdn.com/w40/{code}.png",
                'code': code
            })
    
    return flags

def create_nationality_component(nationalities_str):
    flags = get_country_flags(nationalities_str)
    
    if not flags:
        return ui.span(f"🌍 {nationalities_str or 'N/A'}")
    
    return ui.div(
        *[ui.span(
            ui.img(src=flag['image_url'],
                 style="height: 20px; margin-right: 5px; border: 1px solid #ddd;",
                 class_name="rounded-circle",
                 title=flag['name']),
            class_name="d-inline-block me-2"
        ) for flag in flags],
        class_name="d-flex flex-wrap align-items-center"
    )
    
def info_card(title, icon, content=None, color="primary"):
    """Función auxiliar para crear tarjetas de información"""
    return ui.div(
        ui.div(
            ui.h4(f"{icon} {title}", class_=f"card-title text-{color}"),
            ui.p(content if content else "", class_="card-text"),
            class_="card-body"
        ),
        class_=f"card border-{color} mb-3"
    )
    

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, f'INFORME DE {self.player_name.upper()}', 0, 1, 'C')
        self.set_font('Arial', '', 10)
        self.cell(0, 10, f'Generado el: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'C')
        self.line(10, 30, 200, 30)
        self.ln(15)
        
    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def generar_pdf(player_info, filename="informe_jugador.pdf"):
    pdf = PDF()
    pdf.player_name = player_info.get('nombre', 'Jugador Desconocido')
    pdf.set_auto_page_break(auto=True, margin=25)
    pdf.add_page()
    
    # Estilo para títulos de sección
    pdf.set_font("Arial", 'B', 14)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 10, "INFORMACIÓN BÁSICA", 0, 1, 'L', 1)
    pdf.ln(5)
    
    # Información básica en dos columnas
    pdf.set_font("Arial", size=11)
    col_width = pdf.w / 2.2
    x = pdf.get_x()
    y = pdf.get_y()
    
    # Excluimos lesiones y logros de la info básica
    basic_info = {k: v for k, v in player_info.items() 
                 if k not in ['lesiones', 'logros', 'imagen_url', 'club_imagen_url', 'estadisticas']}
    items_per_col = (len(basic_info) + 1) // 2
    
    for i, (key, value) in enumerate(basic_info.items()):
        if i < items_per_col:
            pdf.set_xy(x, y + i*8)
        else:
            pdf.set_xy(x + col_width, y + (i-items_per_col)*8)
        
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(40, 8, f"{key.replace('_', ' ').title()}:")
        pdf.set_font("Arial", size=11)
        
        # Manejar diferentes tipos de valores
        if isinstance(value, list):
            value = ', '.join(str(v) for v in value)
        elif isinstance(value, dict):
            value = str(value)
        else:
            value = str(value)
            
        pdf.multi_cell(0, 8, value)
    
    pdf.ln(10)
    
    # Historial de lesiones (usando la nueva estructura de datos)
    if 'lesiones' in player_info and player_info['lesiones']:
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "HISTORIAL DE LESIONES", 0, 1, 'L', 1)
        pdf.ln(5)
        
        # Cabecera de tabla
        headers = ["Temporada", "Tipo", "Inicio", "Fin", "Días", "Partidos"]
        col_widths = [30, 40, 30, 30, 20, 30]
        
        pdf.set_font("Arial", 'B', 11)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 8, header, 1, 0, 'C')
        pdf.ln()
        
        # Datos de lesiones
        pdf.set_font("Arial", size=10)
        for lesion in player_info['lesiones']:
            pdf.cell(col_widths[0], 8, lesion.get('Temporada', 'N/A'), 1)
            pdf.cell(col_widths[1], 8, lesion.get('Tipo', 'N/A'), 1)
            pdf.cell(col_widths[2], 8, lesion.get('Fecha_Inicio', 'N/A'), 1)
            pdf.cell(col_widths[3], 8, lesion.get('Fecha_Fin', 'N/A'), 1)
            pdf.cell(col_widths[4], 8, lesion.get('Dias_Lesionado', 'N/A'), 1)
            pdf.cell(col_widths[5], 8, lesion.get('Partidos_Perdidos', 'N/A'), 1)
            pdf.ln()
        
        # Resumen estadístico
        pdf.ln(5)
        total_dias = sum(int(lesion['Dias_Lesionado'].replace(' días', '')) 
                     for lesion in player_info['lesiones'] 
                     if 'Dias_Lesionado' in lesion and lesion['Dias_Lesionado'].replace(' días', '').isdigit())
        total_partidos = sum(int(lesion['Partidos_Perdidos']) 
                          for lesion in player_info['lesiones'] 
                          if 'Partidos_Perdidos' in lesion and str(lesion['Partidos_Perdidos']).isdigit())
        
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, "Resumen:", 0, 1)
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, f"Total de lesiones: {len(player_info['lesiones'])}", 0, 1)
        pdf.cell(0, 8, f"Días totales lesionado: {total_dias}", 0, 1)
        pdf.cell(0, 8, f"Partidos totales perdidos: {total_partidos}", 0, 1)
    else:
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "HISTORIAL DE LESIONES", 0, 1, 'L', 1)
        pdf.ln(5)
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, "No hay historial de lesiones registrado.", 0, 1)
    
    # Sección de logros (nueva estructura)
    if 'logros' in player_info and player_info['logros']:
        pdf.add_page()
        
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "LOGROS Y TÍTULOS", 0, 1, 'L', 1)
        pdf.ln(5)
        
        # Agrupar por categoría
        logros_df = pd.DataFrame(player_info['logros'])
        grouped = logros_df.groupby('Categoría')
        
        for categoria, grupo in grouped:
            pdf.set_font("Arial", 'B', 12)
            pdf.set_fill_color(220, 220, 220)
            pdf.cell(0, 8, categoria, 0, 1, 'L', 1)
            pdf.ln(2)
            
            # Cabecera de tabla
            headers = ["Temporada", "Club/Detalle"]
            col_widths = [40, 150]
            
            pdf.set_font("Arial", 'B', 11)
            pdf.cell(col_widths[0], 8, headers[0], 1, 0, 'C')
            pdf.cell(col_widths[1], 8, headers[1], 1, 1, 'C')
            
            # Datos
            pdf.set_font("Arial", size=10)
            for _, row in grupo.iterrows():
                pdf.cell(col_widths[0], 8, row['Temporada'], 1)
                pdf.cell(col_widths[1], 8, row['Club'], 1)
                pdf.ln()
            
            pdf.ln(5)
        
        # Resumen estadístico
        total_logros = len(player_info['logros'])
        categorias = len(logros_df['Categoría'].unique())
        
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 8, "Resumen:", 0, 1)
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, f"Total de logros: {total_logros}", 0, 1)
        pdf.cell(0, 8, f"Categorías distintas: {categorias}", 0, 1)
    else:
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(0, 10, "LOGROS Y TÍTULOS", 0, 1, 'L', 1)
        pdf.ln(5)
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 8, "No hay logros registrados.", 0, 1)
    
    # Guardar PDF
    pdf.output(filename)
    return filename

# ======================
# FUNCIONES DE SCRAPING
# ======================

def get_coach_profile_url(query, max_retries=3):
    """Devuelve solo el enlace al perfil del entrenador más relevante en Transfermarkt"""
    base_url = "https://www.transfermarkt.com"
    search_url = f"{base_url}/schnellsuche/ergebnis/schnellsuche?query={quote(query)}"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept-Language': 'es-ES,es;q=0.9',
    }

    for attempt in range(max_retries):
        try:
            response = requests.get(search_url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            all_links = soup.find_all('a', href=True)
            for a in all_links:
                href = a['href'].lower()
                if '/profil/trainer/' in href:
                    return urljoin(base_url, a['href'])

            return None  

        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                return f"Error de conexión después de {max_retries} intentos: {e}"
        except Exception as e:
            return f"Error inesperado: {e}"

def scrape_coach_profile_from_url(url):
    """Scrapes coach profile information from a Transfermarkt coach URL"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # Extraer el ID del entrenador de la URL
        coach_id = url.split('/')[-1]
        
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        coach_data = {'coach_id': coach_id}  # Añadimos el ID al diccionario de datos
        
        profile_box = soup.find('div', class_='spielerdaten')
        if not profile_box:
            return {"Error": "No se encontró el cuadro de datos del perfil"}
        
        rows = profile_box.find_all('tr')
        
        for row in rows:
            th = row.find('th')
            td = row.find('td')
            if not th or not td:
                continue
            
            key = th.get_text(strip=True)
            value = td.get_text(strip=True)
            
            if "Full Name" in key:
                coach_data['nombre_completo'] = value
            
            elif "Date of birth" in key:
                parts = value.split('(')
                coach_data['fecha_nacimiento'] = parts[0].strip()
                if len(parts) > 1:
                    coach_data['edad'] = parts[1].replace(')', '').strip()
            
            elif "Place of Birth" in key:
                span = td.find('span')
                if span:
                    coach_data['lugar_nacimiento'] = span.get_text(strip=True).split('\xa0')[0]
                else:
                    coach_data['lugar_nacimiento'] = value
            
            elif "Citizenship" in key:
                flags = td.find_all('img', class_='flaggenrahmen')
                if flags:
                    coach_data['nacionalidades'] = [flag['title'] for flag in flags]
                else:
                    coach_data['nacionalidades'] = [value]
            
            elif "Avg. term as coach" in key:
                coach_data['media_tiempo_entrenador'] = value.replace('Years', '').strip()
            
            elif "Coaching Licence" in key:
                coach_data['licencia'] = value
            
            elif "Preferred formation" in key:
                coach_data['formacion_preferida'] = value
            
            elif "Agent" in key:
                agent = td.find('a')
                if agent:
                    coach_data['agente'] = agent.get_text(strip=True)
                else:
                    coach_data['agente'] = value
        
        return coach_data
    
    except requests.exceptions.RequestException as e:
        return {"Error": f"Error de conexión: {str(e)}"}
    except Exception as e:
        return {"Error": f"Error al obtener información del entrenador: {str(e)}"}
    
def get_coach_achievements(coach_id):
    """Obtiene los logros del entrenador desde Transfermarkt"""
    url = f'https://www.transfermarkt.com/xabi-alonso/erfolge/trainer/{coach_id}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            table = soup.find('table', class_='items')
            
            data = []
            current_achievement = None
            
            if table:
                for row in table.find_all('tr'):
                    tds = row.find_all('td')
                    
                    # Fila de logro (una sola celda con <strong>)
                    if len(tds) == 1 and row.find('strong'):
                        current_achievement = row.find('strong').get_text(strip=True)
                    
                    # Fila de detalle con datos
                    elif len(tds) > 2 and tds[0].get_text(strip=True):
                        season = tds[0].get_text(strip=True)

                        # Extraer competición
                        competition_img = tds[1].find('img')
                        if competition_img and competition_img.has_attr('title'):
                            competition = competition_img['title']
                        else:
                            competition = tds[1].get_text(strip=True)

                        data.append({
                            'Logro': current_achievement,
                            'Temporada': season,
                            'Competición': competition
                        })

            return pd.DataFrame(data)
        return pd.DataFrame()
    except Exception as e:
        print(f"Error obteniendo logros: {str(e)}")
        return pd.DataFrame()

def get_coach_club_history(name_slug, coach_id):
    url = f'https://www.transfermarkt.es/{name_slug}/stationen/trainer/{coach_id}/plus/1'
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Accept-Language': 'es-ES,es;q=0.9',
    }

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        table = soup.find('table', class_='items')
        if not table:
            return pd.DataFrame(), "No se encontró la tabla"

        data = []
        rows = table.find('tbody').find_all('tr')

        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 14:
                continue

            club = cols[1].find('a').get_text(strip=True)
            rol = cols[1].get_text(strip=True).replace(club, '').strip()
            temporada = cols[2].get_text(strip=True)
            salida = cols[3].get_text(strip=True)
            desde_hasta = cols[4].get_text(strip=True).replace('\n', '').replace(' / ', ' / ')
            duracion = cols[5].get_text(strip=True)
            partidos = cols[6].get_text(strip=True)
            ganados = cols[7].get_text(strip=True)
            empatados = cols[8].get_text(strip=True)
            perdidos = cols[9].get_text(strip=True)
            jugadores = cols[10].get_text(strip=True)
            goles = cols[11].get_text(strip=True)
            ppp = cols[12].get_text(strip=True)
            resumen = cols[13].get_text(strip=True)

            data.append({
                "Club": club,
                "Rol": rol,
                "Temporada": temporada,
                "Salida": salida,
                "Duración": duracion,
                "Partidos": partidos,
                "Ganados": ganados,
                "Empatados": empatados,
                "Perdidos": perdidos,
                "Jugadores usados": jugadores,
                "Goles pro/contra": goles,
                "Puntos por partido": ppp,
            })

        return pd.DataFrame(data), None

    except requests.exceptions.RequestException as e:
        return pd.DataFrame(), f"Error de conexión: {str(e)}"
    except Exception as e:
        return pd.DataFrame()(), f"Error inesperado: {str(e)}"
    
def generar_pdf_entrenador(coach_info, club_history, achievements, filename="informe_entrenador.pdf"):
    pdf = PDF()
    pdf.player_name = coach_info.get('nombre_completo', 'Entrenador Desconocido')
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Estilo para títulos de sección
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 8, "INFORMACIÓN BÁSICA", 0, 1, 'L', 1)
    pdf.ln(3)
    
    # Información básica en dos columnas bien alineadas
    pdf.set_font("Arial", size=10)
    basic_info = {k: v for k, v in coach_info.items() if k not in ['coach_id', 'lesiones', 'logros', 'imagen_url']}
    
    col1 = list(basic_info.items())[:len(basic_info)//2 + len(basic_info)%2]
    col2 = list(basic_info.items())[len(basic_info)//2 + len(basic_info)%2:]

    max_rows = max(len(col1), len(col2))
    row_height = 6
    label_width = 45
    value_width = 50

    x_start = pdf.get_x()
    y_start = pdf.get_y()

    for i in range(max_rows):
        pdf.set_xy(x_start, y_start + i * row_height)
        # Columna 1
        if i < len(col1):
            key, value = col1[i]
            if isinstance(value, list):
                value = ', '.join(value)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(label_width, row_height, f"{key.replace('_', ' ').title()}:", 0)
            pdf.set_font("Arial", size=10)
            pdf.cell(value_width, row_height, str(value), 0)
        else:
            pdf.cell(label_width + value_width, row_height, '', 0)

        # Columna 2
        if i < len(col2):
            key, value = col2[i]
            if isinstance(value, list):
                value = ', '.join(value)
            pdf.set_font("Arial", 'B', 10)
            pdf.cell(label_width, row_height, f"{key.replace('_', ' ').title()}:", 0)
            pdf.set_font("Arial", size=10)
            pdf.cell(value_width, row_height, str(value), 0)
        pdf.ln(row_height)

    pdf.ln(5)

    # Historial de clubes
    if not club_history.empty:
        if pdf.get_y() > 200:
            pdf.add_page()
        else:
            pdf.ln(3)

        pdf.set_font("Arial", 'B', 13)
        pdf.cell(0, 8, "HISTORIAL DE CLUBES", 0, 1, 'L', 1)
        pdf.ln(3)

        pdf.set_font("Arial", size=9)
        pdf.set_draw_color(200, 200, 200)
        pdf.set_line_width(0.3)

        headers = ["Club", "Temporada", "Duración", "Partidos", "G-E-P", "PPP"]
        col_widths = [40, 25, 25, 18, 28, 18]

        pdf.set_font("Arial", 'B', 9)
        for j, header in enumerate(headers):
            pdf.cell(col_widths[j], 6, header, 1, 0, 'C')
        pdf.ln()

        pdf.set_font("Arial", size=8)
        for _, row in club_history.iterrows():
            club = row['Club'][:20] + '...' if len(row['Club']) > 20 else row['Club']
            temporada = row['Temporada'][:9]
            duracion = row['Duración'][:9]
            partidos = str(row['Partidos'])
            resultados = f"{row['Ganados']}-{row['Empatados']}-{row['Perdidos']}"
            ppp = str(row['Puntos por partido'])

            pdf.cell(col_widths[0], 6, club, 1)
            pdf.cell(col_widths[1], 6, temporada, 1)
            pdf.cell(col_widths[2], 6, duracion, 1)
            pdf.cell(col_widths[3], 6, partidos, 1)
            pdf.cell(col_widths[4], 6, resultados, 1)
            pdf.cell(col_widths[5], 6, ppp, 1)
            pdf.ln()

            if pdf.get_y() > 270:
                pdf.add_page()
                pdf.set_font("Arial", 'B', 9)
                for j, header in enumerate(headers):
                    pdf.cell(col_widths[j], 6, header, 1, 0, 'C')
                pdf.ln()
                pdf.set_font("Arial", size=8)
    else:
        pdf.set_font("Arial", 'B', 13)
        pdf.cell(0, 8, "HISTORIAL DE CLUBES", 0, 1, 'L', 1)
        pdf.ln(2)
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 6, "No hay historial de clubes registrado.", 0, 1)

    # Sección de logros
    if not achievements.empty:
        if pdf.get_y() > 230:
            pdf.add_page()
        else:
            pdf.ln(3)

        pdf.set_font("Arial", 'B', 13)
        pdf.cell(0, 8, "LOGROS Y TÍTULOS", 0, 1, 'L', 1)
        pdf.ln(3)

        grouped = achievements.groupby('Logro')

        for categoria, grupo in grouped:
            if pdf.get_y() > 250:
                pdf.add_page()

            pdf.set_font("Arial", 'B', 11)
            pdf.set_fill_color(220, 220, 220)
            pdf.cell(0, 6, categoria, 0, 1, 'L', 1)
            pdf.ln(1)

            col_widths = [30, 70]
            pdf.set_draw_color(200, 200, 200)
            pdf.set_line_width(0.3)

            pdf.set_font("Arial", 'B', 9)
            pdf.cell(col_widths[0], 6, "Temporada", 1, 0, 'C')
            pdf.cell(col_widths[1], 6, "Competición", 1, 1, 'C')

            pdf.set_font("Arial", size=8)
            for _, row in grupo.iterrows():
                pdf.cell(col_widths[0], 6, row['Temporada'], 1)
                pdf.cell(col_widths[1], 6, row['Competición'][:45], 1)
                pdf.ln()

                if pdf.get_y() > 270:
                    pdf.add_page()
                    pdf.set_font("Arial", 'B', 9)
                    pdf.cell(col_widths[0], 6, "Temporada", 1, 0, 'C')
                    pdf.cell(col_widths[1], 6, "Competición", 1, 1, 'C')
                    pdf.set_font("Arial", size=8)
            pdf.ln(3)
    else:
        pdf.set_font("Arial", 'B', 13)
        pdf.cell(0, 8, "LOGROS Y TÍTULOS", 0, 1, 'L', 1)
        pdf.ln(2)
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 6, "No hay logros registrados.", 0, 1)

    # Guardar PDF
    pdf.output(filename)
    return filename

def parse_to_mean(value):
    """Convierte strings de números separados por comas a float promedio"""
    try:
        if isinstance(value, str) and ',' in value:
            numbers = [float(x.strip()) for x in value.split(',')]
            return sum(numbers) / len(numbers)
        return float(value)
    except Exception:
        return None

def get_player_impect_scores(player_name):
    """Obtiene los scores de impect del jugador desde df2"""
    if not player_name:
        return None
        
    player_data = df2[df2['playerName'] == player_name].copy()
    if player_data.empty:
        return None

    # Limpiar y convertir las columnas necesarias
    columns = [
        'IMPECT_SCORE_PACKING',
        'IMPECT_SCORE_WITHOUT_GOALS_PACKING',
        'OFFENSIVE_IMPECT_SCORE_PACKING',
        'DEFENSIVE_IMPECT_SCORE_PACKING'
    ]

    for col in columns:
        player_data[col] = player_data[col].apply(parse_to_mean)

    # Calcular los promedios
    scores = {col: player_data[col].mean() for col in columns}
    
    # Redondear valores
    return {k: round(v, 2) for k, v in scores.items() if not pd.isna(v)}


# --- Definiciones de Features y Grupos ---
general_features = [
    'IMPECT_SCORE_PACKING', 'SCORER_SCORE', 'PROGRESSION_SCORE_PACKING',
    'OFFENSIVE_IMPECT_SCORE_PACKING', 'RECEIVING_SCORE_PACKING', 'INTERVENTIONS_SCORE_PACKING',
    'DEFENSIVE_POSITIONAL_PLAY_SCORE_PACKING', 'GROUND_DUEL_SCORE', 'INTERCEPTION_SCORE'
]
offensive_features = [
    'SCORER_SCORE', 'PROGRESSION_SCORE_PACKING', 'OFFENSIVE_IMPECT_SCORE_PACKING',
    'LOW_PASS_SCORE', 'DIAGONAL_PASS_SCORE', 'DRIBBLE_SCORE', 'CLOSE_RANGE_SHOT_SCORE',
    'OFFENSIVE_HEADER_SCORE', 'LONG_RANGE_SHOT_SCORE', 'MID_RANGE_SHOT_SCORE',
    'OPEN_GOAL_SHOT_SCORE', 'RATIO_SHOTS_ON_TARGET', 'RATIO_GOALS_SHOT_XG', 'RATIO_SHOTS_PER_GOAL',
]
defensive_features = [
    'DEFENSIVE_POSITIONAL_PLAY_SCORE_PACKING', 'DEFENSIVE_IMPECT_SCORE_PACKING',
    'INTERVENTIONS_SCORE_PACKING', 'CLEARANCE_SCORE', 'LOOSE_BALL_REGAIN_SCORE',
    'INTERCEPTION_SCORE', 'GROUND_DUEL_SCORE', 'BLOCK_SCORE', 'DEFENSIVE_HEADER_SCORE',
    'RATIO_AERIAL_DUELS', 'RATIO_GROUND_DUELS',
]
aerial_features = [
    'OFFENSIVE_HEADER_SCORE', 'DEFENSIVE_HEADER_SCORE', 'RATIO_AERIAL_DUELS',
    'AERIAL_DUELS_NUMBER', 'AERIAL_DUELS_NUMBER_IN_PACKING_ZONE_CB'
]
passing_features = [
    'RECEIVING_SCORE_PACKING', 'LOW_PASS_SCORE', 'LOW_CROSS_SCORE', 'HIGH_CROSS_SCORE',
    'DIAGONAL_PASS_SCORE', 'CHIPPED_PASS_SCORE', 'SHORT_AERIAL_PASS_SCORE',
    'RATIO_PASSING_ACCURACY', 'SUCCESSFUL_PASSES_CLEAN', 'UNSUCCESSFUL_PASSES_CLEAN'
]

groups = {
    'General': general_features,
    'Ofensivo': offensive_features,
    'Defensivo': defensive_features,
    'Juego Aéreo': aerial_features,
    'Pase y Recepción': passing_features
}

group_colors = {
    'General': '#1f77b4',
    'Ofensivo': '#d62728',
    'Defensivo': '#2ca02c',
    'Juego Aéreo': '#ff7f0e',
    'Pase y Recepción': '#9467bd'
}

# --- Funciones de Ayuda y Gráfico ---
def normalize_percentile(col: pd.Series) -> pd.Series:
    
    if col.dtype == object:
        col = col.str.replace(',', '.').astype(float)
        
    if col.nunique() <= 1:
        return pd.Series([0.5] * len(col), index=col.index, name=col.name)
    p10 = np.percentile(col.dropna(), 10)
    p90 = np.percentile(col.dropna(), 90)
    if p90 - p10 == 0:
        return pd.Series([0.5] * len(col), index=col.index, name=col.name)
    normalized_col = np.clip((col - p10) / (p90 - p10), 0, 1)
    return normalized_col

def generate_radar_plot(df_orig: pd.DataFrame, player_name: str, selected_group_name: str, season: str = None):
    if df_orig.empty:
        fig = go.Figure()
        fig.update_layout(title_text="DataFrame original está vacío.", title_x=0.5)
        return fig

    # Filtrar por temporada si se especifica
    if season and season != "Todas":
        df_orig = df_orig[df_orig['season'] == season]

    player_rows = df_orig[df_orig['playerName'] == player_name]
    if player_rows.empty:
        fig = go.Figure()
        fig.update_layout(title_text=f"Jugador '{player_name}' no encontrado.", title_x=0.5)
        return fig
    
    player_row = player_rows.iloc[0] 
    season = player_row.get('season', 'N/A')
    competition = player_row.get('competitionName', 'N/A')
    position_str = str(player_row.get('positions', 'N/A'))
    position = position_str.split(",")[0].strip()
    
    df_filtered = df_orig[
        (df_orig['season'] == season) &
        (df_orig['competitionName'] == competition) &
        (df_orig['positions'].str.contains(position, na=False) if pd.notna(position) and position != 'N/A' else pd.Series(True, index=df_orig.index))
    ].dropna(subset=['playerName'])

    if df_filtered.empty:
        fig = go.Figure()
        fig.update_layout(title_text=f"No hay jugadores comparables para {player_name}", title_x=0.5)
        return fig
    
    features_for_group = groups.get(selected_group_name, [])
    existing_features = [f for f in features_for_group if f in df_filtered.columns]

    if not existing_features:
        fig = go.Figure()
        fig.update_layout(title_text=f"Features no encontradas para grupo '{selected_group_name}'", title_x=0.5)
        return fig

    df_norm = df_filtered.copy()
    for feat in existing_features:
        if df_filtered[feat].notna().any():
            df_norm[feat + "_norm"] = normalize_percentile(df_filtered[feat])
        else:
            df_norm[feat + "_norm"] = 0.5
            
    player_norm_rows = df_norm[df_norm['playerName'] == player_name]
    if player_norm_rows.empty:
        fig = go.Figure()
        fig.update_layout(title_text=f"Jugador no encontrado tras normalizar", title_x=0.5)
        return fig
    player_norm_data = player_norm_rows.iloc[0]

    norm_feats_cols = [f"{f}_norm" for f in existing_features if f"{f}_norm" in df_norm.columns]
    
    if not norm_feats_cols:
        fig = go.Figure()
        fig.update_layout(title_text=f"Columnas normalizadas no encontradas", title_x=0.5)
        return fig

    player_values_norm = player_norm_data[norm_feats_cols].fillna(0.5).values.flatten().tolist()
    player_values_real = player_norm_data[existing_features].fillna(0).values.flatten().tolist()
    avg_values_norm = df_norm[norm_feats_cols].mean().fillna(0.5).values.flatten().tolist()

    player_values_norm_circular = player_values_norm + ([player_values_norm[0]] if player_values_norm else [])
    avg_values_norm_circular = avg_values_norm + ([avg_values_norm[0]] if avg_values_norm else [])
    theta_labels = existing_features + ([existing_features[0]] if existing_features else [])

    hovertext = []
    if len(existing_features) == len(player_values_real) == len(player_values_norm):
        hovertext = [
            f"{feat}<br>Valor real: {val:.2f}<br>Percentil: {pct*100:.1f}%" 
            for feat, val, pct in zip(existing_features, player_values_real, player_values_norm)
        ]
        hovertext_circular = hovertext + ([hovertext[0]] if hovertext else [])
    else: 
        hovertext_circular = [f"{feat}" for feat in theta_labels]

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=player_values_norm_circular, theta=theta_labels, fill='toself', name=player_name,
        line_color=group_colors.get(selected_group_name, '#1f77b4'),
        hovertext=hovertext_circular, hoverinfo="text", marker=dict(size=6),
        fillcolor=group_colors.get(selected_group_name, '#1f77b4'), opacity=0.5
    ))
    fig.add_trace(go.Scatterpolar(
        r=avg_values_norm_circular, theta=theta_labels, name='Promedio Pos. Similar',
        line=dict(color='lightgray', dash='dash'), marker=dict(size=6), hoverinfo='skip'
    ))
    fig.update_layout(
        title=dict(
            text=f"Temporada: {season}, Competición: {competition}",
            font=dict(size=14, color="#1a1a1a"), x=0.5
        ),
        polar=dict(
            radialaxis=dict(
                visible=True, range=[0, 1], showticklabels=True,
                tickvals=[0, 0.25, 0.5, 0.75, 1.0],
                ticktext=["10", "32.5", "55", "77.5", "90"],
                tickfont=dict(size=10), gridcolor="lightgray"
            ),
            angularaxis=dict(tickfont=dict(size=11, color="black"), rotation=90, direction="clockwise", gridcolor="lightgray")
        ),
        showlegend=True,
        legend=dict(orientation="h", xanchor="center", x=0.5, y=-0.15, font=dict(size=10)),
        template="plotly_white", margin=dict(t=100, l=60, r=60, b=120),
        height=400  # Altura fija para cada gráfico
    )
    return fig


# Cargar y preparar datos
def load_data():
    df4 = df3.copy()

    columns_to_keep = [
        'season_name', 'competition_name', 'team_name', 'team_season_matches',
        'BYPASSED_OPPONENTS', 'BALL_LOSS_NUMBER', 'BALL_WIN_NUMBER',
        'GOALS', 'OPPONENT_GOALS', 'CRITICAL_BALL_LOSS_NUMBER', 'ASSISTS',
        'SUCCESSFUL_PASSES', 'UNSUCCESSFUL_PASSES',
        'OFFENSIVE_TOUCHES', 'DEFENSIVE_TOUCHES', 'REVERSE_PLAY_NUMBER'
    ]
    
    df4 = df4[df4['team_season_matches'].isin([1, 14]) == False]
    df4 = df4[columns_to_keep]
    
    selected_columns = [
        'GOALS', 'SUCCESSFUL_PASSES', 'BALL_WIN_NUMBER',
        'BYPASSED_OPPONENTS', 'UNSUCCESSFUL_PASSES',
        'CRITICAL_BALL_LOSS_NUMBER', 'OPPONENT_GOALS'
    ]
    
    # Asegurar que las columnas sean numéricas
    df_selected = df4[selected_columns].copy()
    
    # Escalado con nombres de características
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(df_selected)
    
    # Convertir a DataFrame para mantener nombres
    X_scaled_df = pd.DataFrame(X_scaled, columns=selected_columns, index=df_selected.index)
    
    # Clustering
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    clusters = kmeans.fit_predict(X_scaled_df)
    df4['cluster'] = clusters
    df4['cluster_name'] = 'Cluster ' + df4['cluster'].astype(str)
    
    # t-SNE
    tsne = TSNE(n_components=2, random_state=42, perplexity=min(30, len(X_scaled_df)-1))
    X_tsne = tsne.fit_transform(X_scaled_df)
    df4['TSNE_1'] = X_tsne[:, 0]
    df4['TSNE_2'] = X_tsne[:, 1]
    
    unique_teams = sorted(df4['team_name'].unique())
    team_seasons = {
        team: sorted(df4[df4['team_name'] == team]['season_name'].unique())
        for team in unique_teams
    }
    
    return {
        'df': df4,
        'scaler': scaler,
        'kmeans': kmeans,
        'selected_columns': selected_columns,
        'X_scaled': X_scaled_df,
        'team_seasons': team_seasons,
        'unique_teams': unique_teams
    }
    
data_objects = load_data()
# ======================
# INTERFAZ DE USUARIO (UI)
# ======================
import shiny.render.renderer # Import to access StyleInfo

# Normalizar posiciones
def normalize_position(pos):
    if pd.isna(pos):
        return "Unknown"
    return pos.replace("_", " ").title()

df["positions"] = df["positions"].apply(normalize_position)

POSITION_ORDER = {
    "Goalkeeper": 0,
    "Center Back": 1,
    "Left Back": 2,
    "Right Back": 3,
    "Defensive Midfield": 4,
    "Central Midfield": 5,
    "Left Midfield": 6,
    "Right Midfield": 7,
    "Attacking Midfield": 8,
    "Left Wing": 9,
    "Right Wing": 10,
    "Second Striker": 11,
    "Center Forward": 12,
    "Unknown": 99
}

def get_position_order(pos):
    return POSITION_ORDER.get(pos, 99)


def create_transfermarkt_tab():
    """Crea la pestaña de búsqueda en Transfermarkt con la sección de análisis incluida"""
    return ui.nav_panel("Búsqueda de Jugadores",
        ui.layout_sidebar(
            ui.sidebar(
                ui.input_selectize(
                    "tm_player_select", 
                    "Seleccionar jugador de la base", 
                    choices=[],
                    multiple=False,
                    selected=None
                ),
                ui.input_action_button("tm_search", "Buscar", class_="btn-primary"),
                ui.output_ui("tm_search_status"),
                ui.download_button("download_pdf", "⬇️ Descargar PDF", class_="btn-outline-success mt-2")
            ),
            ui.navset_card_tab(
                ui.nav_panel("Resultados",
                    ui.output_data_frame("tm_results_table"),
                    ui.output_ui("tm_selection_ui")
                ),
                ui.nav_panel("Detalles del Jugador",
                    ui.output_ui("tm_player_details"),
                ),
                ui.nav_panel("📰 Noticias",  
                    ui.output_ui("player_news_ui")
                ),
                ui.nav_panel("🎥 Highlights",  
                    ui.output_ui("player_videos_ui")
                ),
                ui.nav_panel("🤕 Lesiones",  
                    ui.output_ui("player_injuries_ui")
                ),
                ui.nav_panel("🏆 Logros",  
                    ui.output_ui("player_achievements_ui")
                ),
                ui.nav_panel("📊 Análisis Radar",
                    # CSS personalizado para mejorar el diseño
                    ui.tags.head(
                        ui.tags.style("""
                            .card-radar {
                                border: 1px solid #e0e0e0;
                                border-radius: 8px;
                                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                                transition: all 0.3s ease;
                                height: 100%;
                            }
                            .card-radar:hover {
                                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                            }
                            .card-header {
                                background-color: #f8f9fa;
                                border-bottom: 1px solid #e0e0e0;
                                padding: 12px 15px;
                                border-radius: 8px 8px 0 0;
                            }
                            .player-header {
                                background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
                                border-radius: 8px;
                                padding: 20px;
                                margin-bottom: 20px;
                                border: 1px solid #dee2e6;
                            }
                            .badge-stat {
                                font-size: 0.85rem;
                                padding: 5px 10px;
                                margin-right: 8px;
                                margin-bottom: 8px;
                                display: inline-block;
                            }
                            .grid-container {
                                display: grid;
                                grid-template-columns: repeat(auto-fill, minmax(450px, 1fr));
                                gap: 20px;
                                margin-top: 20px;
                            }
                            .top-section {
                                display: flex;
                                gap: 20px;
                                margin-bottom: 20px;
                                align-items: flex-start;
                                flex-wrap: wrap;
                            }
                            .season-selector {
                                background-color: white;
                                padding: 15px;
                                border-radius: 8px;
                                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
                                flex: 1;
                                min-width: 300px;
                            }
                            .info-card {
                                background-color: #f8f9fa;
                                border-radius: 8px;
                                padding: 20px;
                                border: 1px solid #dee2e6;
                                flex: 2;
                                min-width: 300px;
                            }
                            @media (max-width: 768px) {
                                .grid-container {
                                    grid-template-columns: 1fr;
                                }
                                .top-section {
                                    flex-direction: column;
                                }
                            }
                        """)
                    ),
                    ui.output_ui("tm_player_header"),
                    ui.div(
                        ui.div(
                            ui.div(
                                ui.h4("Selección de Temporada", class_="mb-3"),
                                ui.input_select(
                                    "season",
                                    "Temporada:",
                                    choices=[]
                                ),
                                class_="season-selector"
                            ),
                            ui.div(
                                ui.h4("📌 Cómo interpretar los gráficos", class_="mb-3"),
                                ui.p("Cada gráfico radar muestra el rendimiento del jugador en diferentes dimensiones:"),
                                ui.tags.ul(
                                    ui.tags.li("Área azul: Percentil 50 (mediana) para la posición"),
                                    ui.tags.li("Gráfico naranja: Rendimiento del jugador seleccionado"),
                                    ui.tags.li("Valores normalizados (0-100) basados en percentiles 10-90")
                                ),
                                class_="info-card"
                            ),
                            class_="top-section"
                        ),
                        ui.output_ui("all_radar_plots"),
                        class_="px-4"
                    )
                )         
            )
        )
    )
    
def create_coach_tab():
    """Crea la pestaña de vista entrenador con diseño mejorado"""
    return ui.nav_panel("Búsqueda de entrenadores",
        ui.layout_sidebar(
            ui.sidebar(
                ui.input_text("nombre_entrenador", "Nombre del entrenador", 
                            placeholder="Ej: Xabi Alonso, Pep Guardiola"),
                ui.input_action_button("buscar_entrenador", "Buscar", 
                                     class_="btn-primary mt-2"),
                ui.download_button("download_coach_pdf", "⬇️ Descargar Informe", 
                                     class_="btn-outline-success mt-2"),
                width=300
            ),
            ui.div(
                ui.h2("Perfil del Entrenador", class_="mt-3 mb-4 text-center"),
                ui.output_ui("coach_header"),
                ui.navset_card_tab(
                    ui.nav_panel("📊 Información Básica",
                        ui.output_ui("coach_basic_info")
                    ),
                    ui.nav_panel("🧳 Historial de Clubes",
                        ui.output_ui("coach_club_history_display")
                    ),  
                    ui.nav_panel("🏆 Logros",
                        ui.output_ui("coach_achievements_display")
                    ),
                ),
                class_="p-3"
            )
        )
    )

def create_comparison_tab():
    """Crea la pestaña de comparación de jugadores"""
    return ui.nav_panel("Comparación de Jugadores",
        ui.div(
            ui.row(
                # Columna izquierda reducida (solo controles principales)
                ui.column(4,
                    ui.div(
                        ui.h4("Configuración", class_="card-title"),
                        # Selector de métricas
                        ui.div(
                            ui.h4("Selección de Métricas", class_="card-title"),
                            ui.div(
                                ui.output_ui("dynamic_metric_selector"),
                                class_="metric-container"
                            ),
                            class_="card animated"
                        ),
                        ui.div(
                            ui.input_selectize(
                                "players", 
                                ui.div(
                                    ui.span("Jugadores a comparar"),
                                    ui.span(" (selecciona hasta 5)", class_="text-muted")
                                ),
                                choices=[], 
                                multiple=True,
                                options={"maxItems": 5},
                                width="100%"
                            ),
                            class_="card animated"
                        )
                    )
                ),
                
                # Columna derecha más grande (gráfico y selectores de temporada)
                ui.column(8,
                    ui.div(
                        ui.navset_tab(
                            ui.nav_panel(
                                ui.span(ui.HTML('<i class="fas fa-chart-radar mr-2"></i>'), "Gráfico Radar"),
                                ui.div(
                                    output_widget("radar_chart_widget"),
                                    class_="radar-container"
                                ),
                                # Selectores de temporada aparecerán aquí debajo del gráfico
                                ui.output_ui("player_season_selectors"),
                               
                                ui.div(
                                    ui.h4("Grupo de Referencia", class_="card-title"),
                                    ui.input_radio_buttons(
                                        "comparison_group", 
                                        None,
                                        {
                                            "liga": ui.span(ui.HTML('<i class="fas fa-trophy mr-2"></i>'), "Comparar con liga"), 
                                            "equipo": ui.span(ui.HTML('<i class="fas fa-users mr-2"></i>'), "Comparar con equipo"),
                                            "ninguno": ui.span(ui.HTML('<i class="fas fa-times mr-2"></i>'), "Sin comparación")
                                        },
                                        selected="liga"
                                    ),
                                    ui.output_ui("comparison_selector"),
                                    class_="card animated"
                                )
                            ),
                            ui.nav_panel(
                                ui.span("Tabla Comparativa"),
                                ui.div(
                                    ui.output_ui("comparison_table"),
                                    style="max-height: 600px; overflow-y: auto;"
                                )
                            ),
                            id="results_tabs"
                        ),
                        class_="card animated"
                    )
                ),
                class_="mt-4"
            ),
            class_="container-fluid"
        )
    )
    
def create_team_comparison_tab():
    """Crea la pestaña de comparación de equipos"""
    return ui.nav_panel("Comparación de Equipos",
        ui.div(
            ui.row(
                # Columna izquierda reducida (solo controles principales)
                ui.column(4,
                    ui.div(
                        ui.h4("Configuración", class_="card-title"),
                        # Selector de métricas
                        ui.div(
                            ui.h4("Selección de Métricas", class_="card-title"),
                            ui.div(
                                ui.output_ui("dynamic_team_metric_selector"),
                                class_="metric-container"
                            ),
                            class_="card animated"
                        ),
                        ui.div(
                            ui.input_selectize(
                                "teams", 
                                ui.div(
                                    ui.span("Equipos a comparar"),
                                    ui.span(" (selecciona hasta 5)", class_="text-muted")
                                ),
                                choices=[], 
                                multiple=True,
                                options={"maxItems": 5},
                                width="100%"
                            ),
                            class_="card animated"
                        ),
                        ui.div(
                            ui.input_selectize(
                                "competitions", 
                                "Competiciones a incluir",
                                choices=[], 
                                multiple=True,
                                width="100%"
                            ),
                            class_="card animated"
                        )
                    )
                ),
                
                # Columna derecha más grande (gráfico y selectores de temporada)
                ui.column(8,
                    ui.div(
                        ui.navset_tab(
                            ui.nav_panel(
                                ui.span(ui.HTML('<i class="fas fa-chart-radar mr-2"></i>'), "Gráfico Radar"),
                                ui.div(
                                    output_widget("team_radar_chart_widget"),
                                    class_="radar-container"
                                ),
                                # Selectores de temporada aparecerán aquí debajo del gráfico
                                ui.output_ui("team_season_selectors"),
                               
                                ui.div(
                                    ui.h4("Grupo de Referencia", class_="card-title"),
                                    ui.input_radio_buttons(
                                        "team_comparison_group", 
                                        None,
                                        {
                                            "liga": ui.span(ui.HTML('<i class="fas fa-trophy mr-2"></i>'), "Comparar con liga"), 
                                            "ninguno": ui.span(ui.HTML('<i class="fas fa-times mr-2"></i>'), "Sin comparación")
                                        },
                                        selected="liga"
                                    ),
                                    class_="card animated"
                                )
                            ),
                            ui.nav_panel(
                                ui.span("Tabla Comparativa"),
                                ui.div(
                                    ui.output_ui("team_comparison_table"),
                                    style="max-height: 600px; overflow-y: auto;"
                                )
                            ),
                            ui.nav_panel(
                                ui.span("Evolución Temporal"),
                                ui.div(
                                    ui.input_select(
                                        "trend_metric",
                                        "Selecciona métrica para ver evolución",
                                        choices=[],
                                        width="100%"
                                    ),
                                    output_widget("team_trend_chart"),
                                    class_="mt-3"
                                )
                            ),
                            id="team_results_tabs"
                        ),
                        class_="card animated"
                    )
                ),
                class_="mt-4"
            ),
            class_="container-fluid"
        )
    )

def cretate_similar_tab():
    """Crea la pestaña de comparación de equipos con la app integrada"""
    return ui.nav_panel("Similitud de Equipos",
        ui.navset_tab(
                # Aquí integramos tu aplicación completa
                ui.div(
                    ui.div(
                        ui.tags.head(
                            ui.tags.link(rel="stylesheet", href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css"),
                            ui.tags.link(rel="stylesheet", href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"),
                            ui.tags.link(href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap", rel="stylesheet"),
                            ui.tags.style("""
                                /* Aquí puedes pegar todos los estilos CSS de tu app original */
                                :root {
                                    --primary-color: #3498db;
                                    --secondary-color: #2c3e50;
                                    --accent-color: #e74c3c;
                                    --light-color: #ecf0f1;
                                    --dark-color: #2c3e50;
                                    --success-color: #2ecc71;
                                    --warning-color: #f39c12;
                                    --info-color: #3498db;
                                    --border-radius: 8px;
                                    --box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                                    --transition: all 0.3s ease;
                                }
                                                body {
                                font-family: 'Open Sans', sans-serif;
                                background-color: #f5f7fa;
                                color: #333;
                                line-height: 1.6;
                            }
                            
                            .app-header {
                                background: linear-gradient(135deg, var(--secondary-color), var(--primary-color));
                                color: white;
                                padding: 2rem 0;
                                margin-bottom: 2rem;
                                border-radius: 0 0 var(--border-radius) var(--border-radius);
                                box-shadow: var(--box-shadow);
                            }
                            
                            .app-title {
                                font-weight: 700;
                                margin-bottom: 0.5rem;
                                font-size: 2.2rem;
                            }
                            
                            .app-subtitle {
                                font-weight: 400;
                                opacity: 0.9;
                                font-size: 1.1rem;
                            }
                            
                            .card {
                                background-color: white;
                                border-radius: var(--border-radius);
                                box-shadow: var(--box-shadow);
                                padding: 1.5rem;
                                margin-bottom: 1.5rem;
                                border: none;
                                transition: var(--transition);
                            }
                            
                            .card:hover {
                                box-shadow: 0 10px 15px rgba(0, 0, 0, 0.1);
                                transform: translateY(-2px);
                            }
                            
                            .card-title {
                                color: var(--secondary-color);
                                font-weight: 600;
                                margin-bottom: 1.2rem;
                                padding-bottom: 0.5rem;
                                border-bottom: 2px solid var(--light-color);
                            }
                            
                            .btn-primary {
                                background-color: var(--primary-color);
                                border: none;
                                border-radius: var(--border-radius);
                                padding: 0.5rem 1.2rem;
                                font-weight: 600;
                                transition: var(--transition);
                            }
                            
                            .btn-primary:hover {
                                background-color: #2980b9;
                                transform: translateY(-1px);
                            }
                            
                            .form-control, .selectize-input {
                                border-radius: var(--border-radius);
                                border: 1px solid #ddd;
                                padding: 0.5rem 0.75rem;
                                transition: var(--transition);
                            }
                            
                            .form-control:focus, .selectize-input.focus {
                                border-color: var(--primary-color);
                                box-shadow: 0 0 0 0.2rem rgba(52, 152, 219, 0.25);
                            }
                            
                            .selectize-dropdown {
                            z-index: 1050 !important;
                            }

                            .nav-tabs {
                                border-bottom: 4px solid #e2e8f0;
                            }
                            
                            .nav-tabs .nav-link {
                                color: #64748b;
                                font-weight: 800;
                                border: none;
                                padding: 0.75rem 1.5rem;
                                transition: var(--transition);
                            }
                            
                            .nav-tabs .nav-link:hover {
                                color: var(--primary-color);
                                background-color: #f8fafc;
                            }
                            
                            .nav-tabs .nav-link.active {
                                color: var(--primary-color);
                                background-color: transparent;
                                border-bottom: 4px solid var(--primary-color);
                            }
                            
                            /* Radar chart container */
                            .radar-container {
                                height: 500px;
                                margin-bottom: 1rem;
                                width: 100%;
                                position: relative;
                            }
                            
                            .team-profile {
                                border-left: 4px solid;
                                padding-left: 15px;
                            }
                            
                            .team1-profile {
                                border-color: #dc3545;
                            }
                            
                            .team2-profile {
                                border-color: #0d6efd;
                            }
                            
                            .similarity-badge {
                                font-size: 0.9rem;
                                padding: 0.35em 0.65em;
                            }
                            
                            .similarity-card {
                                min-height: 300px;
                            }
                            
                            .cluster-plot-container {
                                height: 600px;
                                margin-top: 20px;
                            }
                            
                            .main-container {
                                max-width: 95%;
                                margin: 0 auto;
                                padding-bottom: 2rem;
                            }
                            
                            @media (max-width: 768px) {
                                .radar-container {
                                    height: 400px;
                                }
                            }
                        """)
                        ),
                        ui.layout_sidebar(
                            ui.sidebar(
                                ui.h4("Parámetros de Comparación", class_="card-title"),
                                ui.input_selectize(
                                    "team1_name", 
                                    "Equipo 1",
                                    choices=data_objects['unique_teams'],
                                    selected=data_objects['unique_teams'][0] if data_objects['unique_teams'] else None
                                ),
                                ui.input_selectize(
                                    "team1_season", 
                                    "Temporada",
                                    choices=[],
                                    selected=None
                                ),
                                ui.input_selectize(
                                    "team2_name", 
                                    "Equipo 2",
                                    choices=data_objects['unique_teams'],
                                    selected=data_objects['unique_teams'][1] if len(data_objects['unique_teams']) > 1 else None
                                ),
                                ui.input_selectize(
                                    "team2_season", 
                                    "Temporada",
                                    choices=[],
                                    selected=None
                                ),
                                width=300
                            ),
                            ui.navset_tab(
                                ui.nav_panel(
                                    "Comparación Directa",
                                    ui.layout_columns(
                                        ui.card(
                                            ui.card_header("Perfil del Equipo 1"),
                                            ui.output_ui("team1_card"),
                                            class_="team-profile team1-profile",
                                            height="100%"
                                        ),
                                        ui.card(
                                            ui.card_header("Perfil del Equipo 2"),
                                            ui.output_ui("team2_card"),
                                            class_="team-profile team2-profile",
                                            height="100%"
                                        ),
                                        col_widths=(6, 6),
                                        height="400px"
                                    ),
                                    ui.card(
                                        ui.card_header("Análisis de Similitud"),
                                        ui.output_text("similarity_score"),
                                        class_="text-center py-3 bg-light"
                                    ),
                                    ui.card(
                                        ui.card_header("Comparación Radar"),
                                        output_widget("radar_chart2"),
                                        class_="plot-container"
                                    ),
                                    ui.card(
                                        ui.card_header("Posición en el Espacio de Clústeres"),
                                        output_widget("tsne_plot"),
                                        class_="plot-container"
                                    )
                                ),
                                ui.nav_panel(
                                    "Equipos Similares",
                                    ui.layout_columns(
                                        ui.card(
                                            ui.card_header(ui.output_text("similar_teams_team1_title")),
                                            ui.output_ui("similar_teams_team1"),
                                            class_="similarity-card"
                                        ),
                                        ui.card(
                                            ui.card_header(ui.output_text("similar_teams_team2_title")),
                                            ui.output_ui("similar_teams_team2"),
                                            class_="similarity-card"
                                        ),
                                        col_widths=(6, 6)
                                    ),
                                    ui.card(
                                        ui.card_header("Características de los Clústeres"),
                                        output_widget("cluster_heatmap"),
                                        class_="plot-container"
                                    )
                                )
                            )
                        ),
                        class_="main-container"
                    )
                )))
    
def create_table_filters():
    """Crea los controles de filtrado para la tabla"""
    return ui.div(
        {"class": "table-filters"},
        ui.div(
            {"class": "filter-group"},
            ui.div({"class": "filter-label"}, "Competición"),
            ui.input_select(
                "competition_filter",
                "",
                choices=["Todos"] + sorted(df["competitionName"].dropna().astype(str).unique().tolist()),
                width="100%"
            )
        ),
        ui.div(
            {"class": "filter-group"},
            ui.div({"class": "filter-label"}, "Equipo"),
            ui.input_select(
                "team_filter",
                "",
                choices=["Todos"] + sorted(df["squadName"].dropna().astype(str).unique().tolist()),
                width="100%"
            )
        ),
        ui.div(
            {"class": "filter-group"},
            ui.div({"class": "filter-label"}, "Posición"),
            ui.input_select(
                "position_filter",
                "",
                choices=["Todos"] + sorted(df["positions"].dropna().astype(str).unique().tolist()),
                width="100%"
            )
        ),
        ui.div(
            {"class": "filter-group"},
            ui.div({"class": "filter-label"}, "Pierna"),
            ui.input_select(
                "leg_filter",
                "",
                choices=["Todos"] + sorted(df["leg"].dropna().astype(str).unique().tolist()),
                width="100%"
            )
        )
    )
    
def create_table_controls():
    """Crea los controles de la tabla (filtros + botones)"""
    return ui.div(
        {"class": "table-controls"},
        ui.input_action_button(
            "reset_filters",
            "Restablecer filtros",
            class_="reset-btn"
        ),
        create_table_filters()
    )

def create_table_footer():
    """Crea el pie de tabla con paginación e información"""
    return ui.div(
        {"class": "table-footer"},
        ui.div(
            {"class": "table-info"},
            ui.output_text("table_info")
        ),
        ui.div(
            {"class": "pagination-controls"},
            ui.tags.button(
                "Anterior",
                id="prev_btn",
                class_="btn",
                onclick="Shiny.setInputValue('page_change', 'prev', {priority: 'event'});"
            ),
            ui.span(
                ui.output_text("page_info"),
                class_="page-info"
            ),
            ui.tags.button(
                "Siguiente",
                id="next_btn",
                class_="btn",
                onclick="Shiny.setInputValue('page_change', 'next', {priority: 'event'});"
            )
        )
    )
    
def create_player_tab():
    """Crea la pestaña de jugadores con todos los componentes"""
    return ui.nav_panel(
        "Odrecimientos de jugadores",
        ui.div(
            {"class": "table-container"},
            ui.h2("Tabla de jugadores", class_="table-title"),
            create_table_controls(),
            ui.output_ui("tabla_jugadores_html"),
            create_table_footer()
        )
    )

    
app_ui = ui.page_fluid(
    ui.output_text_verbatim("df3_status"),
    ui.tags.link(rel="stylesheet", href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css"),
    ui.tags.link(href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap", rel="stylesheet"),
    ui.tags.style("""
        :root {
            --primary-color: #3498db;
            --secondary-color: #2c3e50;
            --accent-color: #e74c3c;
            --light-color: #ecf0f1;
            --dark-color: #2c3e50;
            --success-color: #2ecc71;
            --warning-color: #f39c12;
            --info-color: #3498db;
            --border-radius: 8px;
            --box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            --transition: all 0.3s ease;
        }
        
        body {
            font-family: 'Open Sans', sans-serif;
            background-color: #f5f7fa;
            color: #333;
            line-height: 1.6;
        }
        
        /* Header styles */
        .app-header {
            background: linear-gradient(135deg, var(--secondary-color), var(--primary-color));
            color: white;
            padding: 2rem 0;
            margin-bottom: 2rem;
            border-radius: 0 0 var(--border-radius) var(--border-radius);
            box-shadow: var(--box-shadow);
        }
        
        .app-title {
            font-weight: 700;
            margin-bottom: 0.5rem;
            font-size: 2.2rem;
        }
        
        .app-subtitle {
            font-weight: 400;
            opacity: 0.9;
            font-size: 1.1rem;
        }
        
        /* Card styles */
        .card {
            background-color: white;
            border-radius: var(--border-radius);
            box-shadow: var(--box-shadow);
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            border: none;
            transition: var(--transition);
        }
        
        .card:hover {
            box-shadow: 0 10px 15px rgba(0, 0, 0, 0.1);
            transform: translateY(-2px);
        }
        
        .card-title {
            color: var(--secondary-color);
            font-weight: 600;
            margin-bottom: 1.2rem;
            padding-bottom: 0.5rem;
            border-bottom: 2px solid var(--light-color);
        }
        
        /* Button and input styles */
        .btn-primary {
            background-color: var(--primary-color);
            border: none;
            border-radius: var(--border-radius);
            padding: 0.5rem 1.2rem;
            font-weight: 600;
            transition: var(--transition);
        }
        
        .btn-primary:hover {
            background-color: #2980b9;
            transform: translateY(-1px);
        }
        
        .form-control, .selectize-input {
            border-radius: var(--border-radius);
            border: 1px solid #ddd;
            padding: 0.5rem 0.75rem;
            transition: var(--transition);
        }
        
        .form-control:focus, .selectize-input.focus {
            border-color: var(--primary-color);
            box-shadow: 0 0 0 0.2rem rgba(52, 152, 219, 0.25);
        }
        
        .selectize-dropdown {
           z-index: 1050 !important;
        }

        /* Metric selector styles */
        .metric-container {
            max-height: 800px;
            overflow-y: auto;
            padding: 1rem;
            background-color: #f8fafc;
            border-radius: var(--border-radius);
            border: 1px solid #e2e8f0;
            margin-bottom: 1rem;
        }
        
        .metric-category {
            margin-bottom: 1rem;
            border: 1px solid #e2e8f0;
            border-radius: var(--border-radius);
            overflow: hidden;
            transition: var(--transition);
        }
        
        .metric-category:hover {
            border-color: var(--primary-color);
        }
        
        .metric-category-header {
            background: linear-gradient(to right, var(--secondary-color), var(--dark-color));
            color: white;
            padding: 0.75rem 1rem;
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: var(--transition);
        }
        
        .metric-category-header:hover {
            background: linear-gradient(to right, var(--dark-color), var(--secondary-color));
        }
        
        .metric-category-title {
            font-weight: 600;
            margin: 0;
            font-size: 0.95rem;
        }
        
        .metric-category-content {
            padding: 1rem;
            background-color: white;
            display: none;
        }
        
        .metric-items {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 0.75rem;
        }
        
        .metric-item {
            display: flex;
            align-items: center;
            padding: 0.6rem 0.8rem;
            background-color: #f8fafc;
            border-radius: calc(var(--border-radius) - 2px);
            transition: var(--transition);
            border: 1px solid #e2e8f0;
        }
        
        .metric-item:hover {
            background-color: #edf2f7;
            border-color: var(--primary-color);
        }
        
        .metric-checkbox {
            margin-right: 0.75rem;
            accent-color: var(--primary-color);
        }
        
        /* Table styles */
        .data-table {
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            font-family: 'Open Sans', sans-serif;
            border-radius: var(--border-radius);
            overflow: hidden;
        }
        
        .data-table th {
            background: linear-gradient(to right, var(--secondary-color), var(--dark-color));
            color: white;
            padding: 0.75rem 1rem;
            text-align: left;
            position: sticky;
            top: 0;
            font-weight: 600;
        }
        
        .data-table td {
            padding: 0.75rem 1rem;
            border-bottom: 1px solid #e2e8f0;
        }
        
        .data-table tr:nth-child(even) {
            background-color: #f8fafc;
        }
        
        .data-table tr:hover {
            background-color: #edf2f7;
        }
        
        .highlight-cell {
            font-weight: 600;
            color: var(--secondary-color);
        }
        
        .comparison-badge {
            display: inline-block;
            padding: 0.25rem 0.6rem;
            border-radius: 1rem;
            font-size: 0.8rem;
            font-weight: 600;
            background-color: #e3f2fd;
            color: var(--primary-color);
        }
        
        /* Tab styles */
        .nav-tabs {
            border-bottom: 4px solid #e2e8f0;
        }
        
        .nav-tabs .nav-link {
            color: #64748b;
            font-weight: 800;
            border: none;
            padding: 0.75rem 1.5rem;
            transition: var(--transition);
        }
        
        .nav-tabs .nav-link:hover {
            color: var(--primary-color);
            background-color: #f8fafc;
        }
        
        .nav-tabs .nav-link.active {
            color: var(--primary-color);
            background-color: transparent;
            border-bottom: 4px solid var(--primary-color);
        }
        
        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 12px;
            height: 12px;
        }
        
        ::-webkit-scrollbar-track {
            background: #f1f1f1;
            border-radius: 12px;
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--primary-color);
            border-radius: 12px;
        }
        
        ::-webkit-scrollbar-thumb:hover {
            background: #2980b9;
        }
        
        /* Responsive adjustments */
        @media (max-width: 850px) {
            .metric-items {
                grid-template-columns: 1fr;
            }
            
            .radar-container {
                height: 500px;
            }
        }
        
        /* Animation */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .animated {
            animation: fadeIn 0.5s ease-out;
        }
        
        /* Radar chart container - AHORA MÁS GRANDE */
        .radar-container {
            height: 500px;  /* Aumentado de 700px */
            margin-bottom: 1rem;
            width: 80%;
            position: relative;
        }
        
        /* Season selectors container - NUEVO ESTILO */
        .season-selectors-wrapper {
            background-color: #f8fafc;
            border-radius: var(--border-radius);
            padding: 1.5rem;
            margin-top: 1.5rem;
            border: 1px solid #e2e8f0;
        }
        
        .season-selectors-container {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 1.2rem;
            margin-top: 0.5rem;
        }
        
        .season-selector-card {
            background-color: white;
            border-radius: var(--border-radius);
            box-shadow: var(--box-shadow);
            padding: 1.2rem;
            transition: var(--transition);
            border: 1px solid #e2e8f0;
            display: flex;
            flex-direction: column;
        }
        
        .season-selector-card:hover {
            box-shadow: 0 8px 12px rgba(0, 0, 0, 0.1);
            border-color: var(--primary-color);
            transform: translateY(-2px);
        }
        
        .season-selector-title {
            font-weight: 600;
            color: var(--secondary-color);
            margin-bottom: 0.75rem;
            font-size: 1rem;
            display: flex;
            align-items: center;
        }
        
        .season-selector-title i {
            margin-right: 0.5rem;
            color: var(--primary-color);
        }
        
        .main-content-container {
            padding-bottom: 2rem;
        }

        /* Fix para el dropdown de selectize */
        .selectize-dropdown {
            z-index: 1050 !important;
        }
        
        /* Player card styles */
        .player-card {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            transition: all 0.3s ease;
            height: 100%;
        }
        
        .player-card:hover {
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }
        
        .card-header {
            background-color: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
            padding: 12px 15px;
            border-radius: 8px 8px 0 0;
        }
        
        .player-header {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid #dee2e6;
        }
        
        .badge-stat {
            font-size: 0.85rem;
            padding: 5px 10px;
            margin-right: 8px;
            margin-bottom: 8px;
            display: inline-block;
        }
        
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(450px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        
        .top-section {
            display: flex;
            gap: 20px;
            margin-bottom: 20px;
            align-items: flex-start;
            flex-wrap: wrap;
        }
        
        .season-selector {
            background-color: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            flex: 1;
            min-width: 300px;
        }
        
        .info-card {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 20px;
            border: 1px solid #dee2e6;
            flex: 2;
            min-width: 300px;
        }
        
        @media (max-width: 768px) {
            .grid-container {
                grid-template-columns: 1fr;
            }
            .top-section {
                flex-direction: column;
            }
        }
        
        /* Badges de comparación */
        .comparison-badge {
            display: inline-block;
            padding: 0.15rem 0.5rem;
            border-radius: 1rem;
            font-size: 0.65rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .top-percentile {
            background-color: rgba(46, 204, 113, 0.15);
            color: var(--success-color);
            border: 1px solid rgba(46, 204, 113, 0.3);
        }
        
        .good-percentile {
            background-color: rgba(52, 152, 219, 0.15);
            color: var(--primary-color);
            border: 1px solid rgba(52, 152, 219, 0.3);
        }
        
        .avg-percentile {
            background-color: rgba(241, 196, 15, 0.15);
            color: var(--warning-color);
            border: 1px solid rgba(241, 196, 15, 0.3);
        }
        
        /* Controles de tabla */
        .table-container {
            background-color: white;
            border-radius: var(--border-radius);
            box-shadow: var(--box-shadow);
            padding: 20px;
            margin: 20px;
            overflow-x: auto;
        }
        
        .table-title {
            color: var(--secondary-color);
            font-weight: 700;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid #e2e8f0;
        }
        
        .table-controls {
            display: flex;
            justify-content: flex-start;
            margin-bottom: 15px;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }
        
        .reset-btn {
            background-color: var(--accent-color) !important;
            color: white !important;
            border: none !important;
            margin-right: 15px;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        
        .reset-btn:hover {
            background-color: #c0392b !important;
        }
          .player-name {
            font-weight: 700 !important;
            color: var(--secondary-color) !important;
        }
        .team-name {
            font-weight: 600;
            color: var(--secondary-color);
        }
        .score-cell {
            font-weight: 600;
        }
        .score-90 {
            background-color: rgba(46, 204, 113, 0.3) !important;
        }
        .score-75 {
            background-color: rgba(46, 204, 113, 0.2) !important;
        }
        .score-50 {
            background-color: rgba(241, 196, 15, 0.2) !important;
        }
        .score-25 {
            background-color: rgba(231, 76, 60, 0.1) !important;
        }
        .numeric-cell {
            text-align: right;
        }
        .sort-icon {
            margin-left: 5px;
        }
        .table-controls {
            display: flex;
            justify-content: flex-start;
            margin-bottom: 15px;
            align-items: center;
            flex-wrap: wrap;
            gap: 15px;
        }
        .table-filters {
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
        }
        .filter-group {
            display: flex;
            flex-direction: column;
            min-width: 180px;
        }
        .filter-label {
            font-size: 0.8rem;
            font-weight: 600;
            margin-bottom: 4px;
            color: var(--secondary-color);
        }
        .table-footer {
            display: flex;
            justify-content: space-between;
            margin-top: 15px;
            align-items: center;
            font-size: 0.9rem;
            color: #64748b;
            flex-wrap: wrap;
            gap: 10px;
        }
        .pagination-controls {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        .page-info {
            margin: 0 10px;
        }
        .btn {
            padding: 6px 12px;
            border-radius: 4px;
            border: 1px solid #ddd;
            background-color: white;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn:hover {
            background-color: #f0f0f0;
        }
        .btn-primary {
            background-color: var(--primary-color);
            color: white;
            border-color: var(--primary-color);
        }
        .btn-primary:hover {
            background-color: #2980b9;
        }
        .form-control {
            padding: 6px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 100%;
        }
        .form-select {
            padding: 6px 12px;
            border: 1px solid #ddd;
            border-radius: 4px;
            width: 100%;
        }
        .reset-btn {
            background-color: var(--accent-color) !important;
            color: white !important;
            border: none !important;
            margin-right: 15px;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .reset-btn:hover {
            background-color: #c0392b !important;
        }
        
        .container-fluid {
                max-width: 95%;
                padding: 0 2rem;
            }
            .metric-card {
                transition: transform 0.2s;
            }
            .metric-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 10px 20px rgba(0,0,0,0.1);
            }
            .player-card {
                border-left: 4px solid transparent;
                transition: all 0.2s;
            }
            .player-card:hover {
                border-left-color: #3498db;
                background-color: #f8f9fa;
            }
            .player-rank {
                width: 30px;
                height: 30px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-weight: bold;
                color: white;
            }
            .rank-1 { background-color: #FFD700; }
            .rank-2 { background-color: #C0C0C0; }
            .rank-3 { background-color: #CD7F32; }
            .rank-4, .rank-5 { background-color: #6c757d; }
            .player-score {
                font-weight: bold;
                font-size: 1.1rem;
            }
            .team-badge {
                background-color: #e9ecef;
                border-radius: 12px;
                padding: 2px 8px;
                font-size: 0.8rem;
            }
            .similarity-badge {
                background-color: #e3f2fd;
                color: #1976d2;
                border-radius: 12px;
                padding: 2px 8px;
                font-size: 0.8rem;
                font-weight: bold;
            }
    """),
        ui.navset_tab(
        create_player_tab(),
        create_transfermarkt_tab(),
        create_coach_tab(),
        create_comparison_tab(),
        create_team_comparison_tab(),
        cretate_similar_tab(),
        ui.nav_panel(
            "Recomendación de jugadores",
            ui.div(
                {"class": "summary-container"},
                ui.card(
                    ui.card_header("Opciones de Análisis"),
                    ui.layout_sidebar(
                        ui.sidebar(
                            ui.input_selectize(
                                "selected_team",
                                "Equipo de referencia para similitud",
                                choices=[""] + sorted(data_objects['df']['team_name'].unique().tolist()),
                            ),
                            ui.input_switch(
                                "use_similarity_switch", 
                                "Usar ajuste por similitud", 
                                value=True
                            ),
                            ui.output_ui("team_similarity_info"),
                            width=300
                        ),
                        ui.panel_well(
                            ui.output_ui("resumen_posiciones_html"),
                            ui.output_ui("similarity_warning")
                        )
                    )
                )
            )
        ),
        id="main_tabs"
    )
)


# ======================
# LÓGICA DEL SERVIDOR
# ======================
def server(input, output, session):

    
    # Estado reactivo para Transfermarkt
    tm_results = reactive.Value([])
    tm_results_display = reactive.Value(pd.DataFrame())
    selected_player_data = reactive.Value(None)
    player_videos = reactive.Value([])
    
     # Estado reactivo
    datos = reactive.Value(df.copy())
    current_page = reactive.Value(1)
    rows_per_page = 10
    sort_column = reactive.Value("IMPECT_SCORE_PACKING")
    sort_direction = reactive.Value(False)
    is_resetting = reactive.Value(False)


    # Función para obtener datos filtrados
    def get_filtered_data():
        df_filtered = datos()
        
        if input.competition_filter() != "Todos":
            df_filtered = df_filtered[df_filtered["competitionName"] == input.competition_filter()]
        if input.team_filter() != "Todos":
            df_filtered = df_filtered[df_filtered["squadName"] == input.team_filter()]
        if input.position_filter() != "Todos":
            df_filtered = df_filtered[df_filtered["positions"] == input.position_filter()]
        if input.leg_filter() != "Todos":
            df_filtered = df_filtered[df_filtered["leg"] == input.leg_filter()]
        
        return df_filtered

    # Actualizar opciones de filtros de manera reactiva
    @reactive.Effect
    @reactive.event(input.competition_filter)
    def update_team_filter():
        if is_resetting():
            return
            
        df_filtered = datos()
        if input.competition_filter() != "Todos":
            df_filtered = df_filtered[df_filtered["competitionName"] == input.competition_filter()]
        
        teams = sorted(df_filtered["squadName"].dropna().astype(str).unique().tolist())
        current_team = input.team_filter()
        new_teams = ["Todos"] + teams
        
        if current_team not in new_teams:
            current_team = "Todos"
            
        ui.update_select("team_filter", choices=new_teams, selected=current_team)

    @reactive.Effect
    @reactive.event(input.competition_filter, input.team_filter)
    def update_position_filter():
        if is_resetting():
            return
            
        df_filtered = datos()
        if input.competition_filter() != "Todos":
            df_filtered = df_filtered[df_filtered["competitionName"] == input.competition_filter()]
        if input.team_filter() != "Todos":
            df_filtered = df_filtered[df_filtered["squadName"] == input.team_filter()]
        
        positions = sorted(df_filtered["positions"].dropna().astype(str).unique().tolist())
        current_position = input.position_filter()
        new_positions = ["Todos"] + positions
        
        if current_position not in new_positions:
            current_position = "Todos"
            
        ui.update_select("position_filter", choices=new_positions, selected=current_position)

    @reactive.Effect
    @reactive.event(input.competition_filter, input.team_filter, input.position_filter)
    def update_leg_filter():
        if is_resetting():
            return
            
        df_filtered = datos()
        if input.competition_filter() != "Todos":
            df_filtered = df_filtered[df_filtered["competitionName"] == input.competition_filter()]
        if input.team_filter() != "Todos":
            df_filtered = df_filtered[df_filtered["squadName"] == input.team_filter()]
        if input.position_filter() != "Todos":
            df_filtered = df_filtered[df_filtered["positions"] == input.position_filter()]
        
        legs = sorted(df_filtered["leg"].dropna().astype(str).unique().tolist())
        current_leg = input.leg_filter()
        new_legs = ["Todos"] + legs
        
        if current_leg not in new_legs:
            current_leg = "Todos"
            
        ui.update_select("leg_filter", choices=new_legs, selected=current_leg)

    # Manejar el botón de reset
    @reactive.Effect
    @reactive.event(input.reset_filters)
    def reset_all_filters():
        is_resetting.set(True)
        try:
            with reactive.isolate():
                ui.update_select("competition_filter", selected="Todos")
                ui.update_select("team_filter", selected="Todos")
                ui.update_select("position_filter", selected="Todos")
                ui.update_select("leg_filter", selected="Todos")
                current_page.set(1)
        finally:
            is_resetting.set(False)

    # Datos filtrados y ordenados
    @reactive.Calc
    def filtered_sorted_data():
        df_filtered = get_filtered_data()
        
        if sort_column() in df_filtered.columns:
            df_filtered = df_filtered.sort_values(
                by=sort_column(),
                ascending=not sort_direction()
            )
        
        return df_filtered

    @reactive.Calc
    def calculate_percentiles():
        df_filtered = filtered_sorted_data()
        score_columns = [
            "IMPECT_SCORE_PACKING", 
            "IMPECT_SCORE_WITHOUT_GOALS_PACKING", 
            "OFFENSIVE_IMPECT_SCORE_PACKING", 
            "DEFENSIVE_IMPECT_SCORE_PACKING"
        ]
        
        percentiles = {}
        
        if 'positions' not in df_filtered.columns or df_filtered.empty:
            return percentiles
        
        # Agrupar por posición
        grouped = df_filtered.groupby('positions')
        
        for position, group in grouped:
            percentiles[position] = {}
            for col in score_columns:
                if col in group.columns and not group[col].empty:
                    try:
                        percentiles[position][col] = {
                            '25': group[col].quantile(0.25),
                            '50': group[col].quantile(0.50),
                            '75': group[col].quantile(0.75),
                            '90': group[col].quantile(0.90)
                        }
                    except:
                        percentiles[position][col] = {
                            '25': 0, '50': 0, '75': 0, '90': 0
                        }
        
        return percentiles

    # Manejar cambios de página
    @reactive.Effect
    @reactive.event(input.page_change)
    def handle_page_change():
        total_pages = max(1, len(filtered_sorted_data()) // rows_per_page + (1 if len(filtered_sorted_data()) % rows_per_page != 0 else 0))
        
        if input.page_change() == "next" and current_page() < total_pages:
            current_page.set(current_page() + 1)
        elif input.page_change() == "prev" and current_page() > 1:
            current_page.set(current_page() - 1)

    # Resetear a página 1 cuando se filtran datos
    @reactive.Effect
    def reset_page_on_filter():
        input.competition_filter()
        input.team_filter()
        input.position_filter()
        input.leg_filter()
        current_page.set(1)

    # Manejar clics en los encabezados de columna
    @reactive.Effect
    @reactive.event(input.sort_column, ignore_none=True)
    def handle_sort():
        if input.sort_column() == sort_column():
            sort_direction.set(not sort_direction())
        else:
            sort_column.set(input.sort_column())
            sort_direction.set(False)
        current_page.set(1)

    # Texto informativo de la tabla
    @output
    @render.text
    def table_info():
        total_rows = len(filtered_sorted_data())
        start_idx = (current_page() - 1) * rows_per_page + 1
        end_idx = min(current_page() * rows_per_page, total_rows)
        return f"Mostrando {start_idx} a {end_idx} de {total_rows} registros"

    # Información de página
    @output
    @render.text
    def page_info():
        total_pages = max(1, len(filtered_sorted_data()) // rows_per_page + (1 if len(filtered_sorted_data()) % rows_per_page != 0 else 0))
        return f"Página {current_page()} de {total_pages}"

    @output
    @render.ui
    def tabla_jugadores_html():
        df_filtered = filtered_sorted_data()
        
        if df_filtered.empty:
            return ui.HTML('<div class="alert alert-info">No se encontraron resultados con los filtros aplicados</div>')
        
        # Calcular el umbral de minutos jugados (60% del máximo)
        max_minutes = df_filtered["playDuration"].max()
        threshold_minutes = 0.4 * max_minutes
        
        # Columnas de score a evaluar
        score_columns = {
            "IMPECT_SCORE_PACKING": "Score General",
            "IMPECT_SCORE_WITHOUT_GOALS_PACKING": "Score General sin Goles",
            "OFFENSIVE_IMPECT_SCORE_PACKING": "Score Ofensivo",
            "DEFENSIVE_IMPECT_SCORE_PACKING": "Score Defensivo"
        }
        
        # Calcular percentiles por columna solo para jugadores que superan el umbral
        percentiles = {}
        qualified_players = df_filtered[df_filtered["playDuration"] >= threshold_minutes]
        
        for col in score_columns:
            if not qualified_players.empty and col in qualified_players.columns:
                percentiles[col] = {
                    'q1': qualified_players[col].quantile(0.25),
                    'median': qualified_players[col].quantile(0.50),
                    'q3': qualified_players[col].quantile(0.75),
                    'q90': qualified_players[col].quantile(0.90)
                }
            else:
                percentiles[col] = None
        
        # Paginación
        start_idx = (current_page() - 1) * rows_per_page
        end_idx = start_idx + rows_per_page
        df_display = df_filtered.iloc[start_idx:end_idx]
        
        # Preparar los datos para mostrar
        display_data = []
        for _, row in df_display.iterrows():
            player_data = {
                "Jugador": row["playerName"],
                "Equipo": row["squadName"],
                "Competición": row["competitionName"],
                "Posición": row["positions"],
                "Pierna": row["leg"],
                "Minutos Jugados": f"{row['playDuration']:.0f}",
            }
            
            # Procesar cada score
            meets_minutes = row["playDuration"] >= threshold_minutes
            for col, display_name in score_columns.items():
                if col not in row or pd.isna(row[col]):
                    player_data[display_name] = "-"
                    continue
                
                value = row[col]
                formatted_value = f"{value:.2f}"
                
                if meets_minutes and percentiles.get(col):
                    p = percentiles[col]
                    if value >= p['q90']:
                        badge = '<span class="comparison-badge top-percentile">TOP 10%</span>'
                    elif value >= p['q3']:
                        badge = '<span class="comparison-badge good-percentile">TOP 25%</span>'
                    elif value >= p['median']:
                        badge = '<span class="comparison-badge avg-percentile">MEDIA</span>'
                    else:
                        badge = ''
                    
                    player_data[display_name] = f'<div class="score-container">{formatted_value}{badge}</div>'
                else:
                    player_data[display_name] = formatted_value
            
            display_data.append(player_data)
        
        # Convertir a DataFrame para facilitar el renderizado
        display_df = pd.DataFrame(display_data)
        
        # Convertir a HTML
        html_table = display_df.to_html(
            classes="data-table",
            escape=False,
            index=False,
            border=0,
            justify="left"
        )
        
        # Aplicar estilo especial a los nombres de jugadores
        html_table = html_table.replace('<td>Jugador', '<td class="highlight-cell">Jugador')
        
        # Reemplazar todas las celdas de nombres de jugadores
        for _, row in df_display.iterrows():
            player_name = row["playerName"]
            html_table = html_table.replace(
                f'<td>{player_name}</td>',
                f'<td class="highlight-cell">{player_name}</td>',
                1
            )
        
        # Estilos CSS personalizados
        styles = """
        <style>
            :root {
                --primary-color: #3498db;
                --secondary-color: #2c3e50;
                --dark-color: #1a252f;
                --success-color: #2ecc71;
                --warning-color: #f39c12;
                --danger-color: #e74c3c;
            }
            
            /* Estilos base de la tabla */
            .data-table {
                width: 100%;
                border-collapse: separate;
                border-spacing: 0;
                font-family: 'Open Sans', sans-serif;
                border-radius: 8px;
                overflow: hidden;
            }
            
            .data-table th {
                background: linear-gradient(to right, var(--secondary-color), var(--dark-color));
                color: white;
                padding: 0.75rem 1rem;
                text-align: left;
                position: sticky;
                top: 0;
                font-weight: 600;
            }
            
            .data-table td {
                padding: 0.75rem 1rem;
                border-bottom: 1px solid #e2e8f0;
                vertical-align: middle;
            }
            
            .data-table tr:nth-child(even) {
                background-color: #f8fafc;
            }
            
            .data-table tr:hover {
                background-color: #edf2f7;
            }
            
            /* Estilo para celdas destacadas */
            .highlight-cell {
                font-weight: 600;
                color: var(--secondary-color);
                border-left: 3px solid var(--primary-color);
                padding-left: 12px !important;
            }
            
            /* Contenedor para scores */
            .score-container {
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 0.5rem;
            }
            
            /* Badges de comparación */
            .comparison-badge {
                display: inline-block;
                padding: 0.15rem 0.5rem;
                border-radius: 1rem;
                font-size: 0.65rem;
                font-weight: 700;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }
            
            .top-percentile {
                background-color: rgba(46, 204, 113, 0.15);
                color: var(--success-color);
                border: 1px solid rgba(46, 204, 113, 0.3);
            }
            
            .good-percentile {
                background-color: rgba(52, 152, 219, 0.15);
                color: var(--primary-color);
                border: 1px solid rgba(52, 152, 219, 0.3);
            }
            
            .avg-percentile {
                background-color: rgba(241, 196, 15, 0.15);
                color: var(--warning-color);
                border: 1px solid rgba(241, 196, 15, 0.3);
            }
            
            /* Efectos hover */
            .data-table tr:hover .highlight-cell {
                color: var(--primary-color);
                background-color: #e3f2fd;
            }
            
            .data-table tr:hover .comparison-badge {
                transform: scale(1.05);
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
        </style>
        """
        
        # Añadir clases de ordenación a los encabezados
        column_mapping = {
            "Jugador": "playerName",
            "Equipo": "squadName",
            "Competición": "competitionName",
            "Posición": "positions",
            "Pierna": "leg",
            "Minutos Jugados": "playDuration",
            **{v: k for k, v in score_columns.items()}
        }
        
        for header in display_df.columns:
            original_col = column_mapping.get(header, header)
            sort_class = ""
            
            if original_col == sort_column():
                sort_class = "sorted-desc" if sort_direction() else "sorted-asc"
            
            onclick = f"Shiny.setInputValue('sort_column', '{original_col}', {{priority: 'event'}});"
            
            html_table = html_table.replace(
                f'<th>{header}</th>',
                f'<th onclick="{onclick}" class="sortable-header {sort_class}">{header}</th>'
            )
        
        return ui.HTML(styles + html_table)
    # ----------------------
    # TRANSFERMARKT SEARCH
    # ----------------------

    player_names_from_df2 = reactive.Value([])
    
    @reactive.effect
    def _load_player_names():
        """Carga los nombres de jugadores de df2 al iniciar"""
        # Asumiendo que df2 tiene una columna 'playerName' con los nombres
        names = sorted(df2['playerName'].unique().tolist())
        player_names_from_df2.set(names)
        
     # Añadir este efecto para actualizar las opciones del select input
    @reactive.effect
    def _update_player_select():
        names = player_names_from_df2()
        ui.update_selectize(
            "tm_player_select",
            choices=names,
            server=True
        )
        
    @reactive.effect
    @reactive.event(input.tm_search)
    async def _search_transfermarkt():
        """Realiza la búsqueda en Transfermarkt"""
        query = input.tm_player_select()
        
        if not query:
            ui.notification_show("Por favor seleccione un jugador de la base", type="error")
            return
        
        with ui.Progress(min=0, max=1) as p:
            p.set(message="Buscando en Transfermarkt...", detail="Esto puede tomar unos segundos")
            
            results = await asyncio.to_thread(sync_get_detailed_transfermarkt_results, query)
            
            if 'Error' in results[0]:
                ui.notification_show(results[0]['Error'], type="error")
                return
            
            tm_results.set(results)
            
            # Crear DataFrame para mostrar
            display_data = []
            for result in results:
                display_data.append({
                    'Nombre': result.get('Nombre', 'N/A'),
                    'Posición': result.get('Posición', 'N/A'),
                    'Club': result.get('Club', 'N/A'),
                    'Edad': result.get('Edad', 'N/A'),
                    'Valor de mercado': result.get('Valor de mercado', 'N/A')
                })
            
            tm_results_display.set(pd.DataFrame(display_data))

    @output
    @render.ui
    def tm_search_status():
        if not input.tm_query():
            return ui.p("Ingrese un nombre de jugador y haga clic en Buscar", class_="text-muted")
        return None
    
    @output
    @render.data_frame
    def tm_results_table():
        df = tm_results_display()
        if df.empty:
            return None
        return render.DataGrid(df, selection_mode="rows")
    
    @output
    @render.ui
    def tm_selection_ui():
        if not tm_results():
            return None
        
        selected_row = input.tm_results_table_selected_rows()
        if not selected_row:
            return ui.p("Seleccione un jugador para ver detalles")
        
        player = tm_results()[selected_row[0]]
        return ui.div(
            ui.h4(f"Jugador seleccionado: {player['Nombre']}"),
            ui.input_action_button("tm_get_details", "Obtener detalles completos", class_="btn-primary mt-2")
        )
    
    @reactive.effect
    @reactive.event(input.tm_get_details)
    async def _get_player_details():
        """Obtiene los detalles completos del jugador seleccionado"""
        selected_row = input.tm_results_table_selected_rows()
        if not selected_row:
            return
        
        player = tm_results()[selected_row[0]]
        
        with ui.Progress(min=0, max=1) as p:
            p.set(message="Obteniendo detalles del jugador...")
            
            # Obtener detalles, imagen y estadísticas
            details_task = asyncio.to_thread(sync_scrape_player_info, player['Enlace'])
            image_task = asyncio.to_thread(google_image_search, player['Nombre'], player.get('Club'))
            club_image_task = asyncio.to_thread(google_club_image_search, player.get('Club'))
            
            player_id = player['Enlace'].split('/')[-1]
            stats_task = asyncio.to_thread(get_player_stats, player_id)
            achievements_task = asyncio.to_thread(get_player_achievements, player_id)
            
            details, image_url, club_image_url, stats_df, achievements_df = await asyncio.gather(
                details_task, image_task, club_image_task, stats_task, achievements_task
            )
            
            details['nombre'] = player['Nombre']
            details['imagen_url'] = image_url
            details['club_imagen_url'] = club_image_url
            details['logros'] = achievements_df.to_dict('records') if not achievements_df.empty else []
            selected_player_data.set(details)
            
    @output
    @render.ui
    def tm_player_details():
        player = selected_player_data()

        if not player:
            return ui.p(
                "Seleccione un jugador y haga clic en 'Obtener detalles' para ver información detallada", 
                class_="text-muted text-center mt-5"
            )

        if 'Error' in player:
            return ui.div(
                ui.h2("Error", class_="text-danger"),
                ui.p(player['Error']),
                class_="alert alert-danger"
            )

        # Reutilizables
        def badge(text, icon):
            return ui.span(
                f"{icon} {text}",
                class_="badge bg-light text-dark me-2 fs-5"
            )

        def player_image_section():
            return ui.div(
                ui.img(
                    src=player.get('imagen_url', 'https://via.placeholder.com/300x350?text=No+Image'),
                    style="width: 100%; max-height: 350px; object-fit: cover; border-radius: 4px;",
                    class_="img-thumbnail mb-3"
                ),
                create_nationality_component(player.get('nacionalidad', '')),
                class_="text-center"
            )

        def club_logo_section():
            return ui.div(
                ui.img(
                    src=player.get('club_imagen_url', 'https://via.placeholder.com/300x350?text=No+Image'),
                    style="max-width: 220px; max-height: 220px; object-fit: contain;",
                    class_="img-thumbnail mb-2"
                ),
                ui.p(player.get('club_actual', ''), class_="text-center small text-muted"),
                class_="text-center"
            )

        def stats_section():
            if not player.get('estadisticas'):
                return ui.div(
                    ui.h4("📊 Estadísticas", class_="mb-3"),
                    ui.p("No hay estadísticas disponibles", class_="text-muted"),
                    class_="p-3 bg-light rounded-3 mb-4"
                )
            
            return ui.div(
                ui.h4("📊 Estadísticas por Temporada", class_="mb-3"),
                ui.output_data_frame("player_stats_table"),
                class_="p-3 bg-light rounded-3 mb-4"
            )
        def impect_scores_section():
            if not player:
                return None
                
            player_name = player.get('nombre')
            scores = get_player_impect_scores(player_name)
            
            if not scores:
                return info_card(
                    title="📊 Scores de Impect",
                    icon="",
                    content="No hay datos de scores disponibles para este jugador",
                    color="secondary"
                )
            
            # Mapeo de columnas a nombres legibles
            score_labels = {
                'IMPECT_SCORE_PACKING': 'Score General',
                'IMPECT_SCORE_WITHOUT_GOALS_PACKING': 'Score sin Goles',
                'OFFENSIVE_IMPECT_SCORE_PACKING': 'Score Ofensivo',
                'DEFENSIVE_IMPECT_SCORE_PACKING': 'Score Defensivo'
            }
            
            # Crear tarjetas para cada score
            score_cards = []
            for key, value in scores.items():
                if key in score_labels:
                    score_cards.append(
                        info_card(
                            title=f"{score_labels[key]}",
                            icon="📊",
                            content=f"{value:.2f}",  # Mostrar con 2 decimales
                            color={
                                'IMPECT_SCORE_PACKING': 'info',
                                'IMPECT_SCORE_WITHOUT_GOALS_PACKING': 'warning',
                                'OFFENSIVE_IMPECT_SCORE_PACKING': 'success',
                                'DEFENSIVE_IMPECT_SCORE_PACKING': 'danger'
                            }.get(key, 'secondary')
                        )
                    )
            
            return ui.div(
                ui.h4("📊 Métricas de Impect", class_="mb-3"),
                ui.layout_columns(
                    *score_cards,
                    col_widths=(3, 3, 3, 3),  # 4 columnas (3 unidades cada una)
                ),
                class_="mb-4"
            )
           
        return ui.div(
            # Cabecera en 3 columnas
            ui.div(
                ui.layout_columns(
                    # Columna 1: Foto
                    player_image_section(),
                    # Columna 2: Info
                    ui.div(
                        ui.h1(player.get('nombre', 'Nombre no disponible'), class_="mb-2"),
                        ui.div(
                            badge(f"{player.get('edad', 'N/A')} años", "📅"),
                            badge(player.get('altura', 'N/A'), "📏"),
                            badge(player.get('pie', 'N/A'), "🦶"),
                            class_="mb-3"
                        ),
                        ui.p(f"🎂 {player.get('fecha_nacimiento', 'N/A')}", class_="mb-1"),
                        ui.p(f"📍 {player.get('lugar_nacimiento', 'N/A')}", class_="mb-1"),
                        class_="d-flex flex-column justify-content-center"
                    ),
                    # Columna 3: Escudo del club
                    club_logo_section(),
                    col_widths=(3, 6, 3),
                    class_="align-items-center mb-4"
                ),
                class_="bg-light p-4 rounded-3 mb-4"
            ),

            # Sección de información principal
            ui.h3("📋 Información del Jugador", class_="mb-3"),
            ui.layout_columns(
                info_card("Posición", "⚽", player.get('posicion', 'N/A'), "info"),
                info_card("Valor de Mercado", "💰", player.get('valor_mercado', 'N/A'), "warning"),
                info_card("Agente", "👔", player.get('agente', 'N/A'), "success"),
                info_card("Contrato hasta", "📝", player.get('contrato_hasta', 'N/A'), "danger"),
                col_widths=(3, 3, 3, 3),
                class_="mb-4"
            ),
            impect_scores_section(),
            class_="p-3",
            style="background-color: #f8f9fa; border-radius: 10px;"
        )
    
    player_news = reactive.Value([])
    
    @reactive.effect
    @reactive.event(input.tm_get_details)
    async def _get_player_news():
        """Obtiene noticias sobre el jugador"""
        selected_row = input.tm_results_table_selected_rows()
        if not selected_row:
            return
        
        player = tm_results()[selected_row[0]]
        
        with ui.Progress(min=0, max=1) as p:
            p.set(message="Buscando noticias...")
            
            try:
                # Usar Google News para buscar noticias
                query = f"{player['Nombre']} {player.get('Club', '')} fútbol"
                news = await asyncio.to_thread(buscar_noticias_deportivas, query)
                player_news.set(news)
            except Exception as e:
                print(f"Error buscando noticias: {e}")
                player_news.set([{"Error": "No se pudieron cargar las noticias"}])
                
                
    @output
    @render.data_frame
    def player_stats_table():
        player = selected_player_data()
        if not player or 'estadisticas' not in player:
            return None
        
        df = pd.DataFrame(player['estadisticas'])
        return render.DataGrid(
            df,
            filters=True,
            width="100%",
            height="400px"
        )               
    
    @output
    @render.ui
    def player_news_ui():
        news = player_news()
        if not news:
            return ui.div(
                ui.h4("📰 Noticias Relevantes", class_="mb-3"),
                ui.div(
                    "No se encontraron noticias periodísticas recientes. Intente con otro jugador.",
                    class_="alert alert-warning"
                ),
                class_="p-3"
            )
        
        news_cards = []
        for i, item in enumerate(news, 1):
            news_cards.append(
                ui.div(
                    ui.div(
                        ui.div(
                            ui.span(f"{i}", class_="badge bg-primary me-2"),
                            ui.span(item['fuente'], class_="text-muted"),
                            class_="d-flex align-items-center mb-2"
                        ),
                        ui.h5(item['titulo'], class_="card-title"),
                        ui.p(item['fecha'], class_="card-text text-muted"),
                        ui.a(
                            "Leer noticia completa", 
                            href=item['enlace'], 
                            target="_blank",
                            class_="btn btn-sm btn-outline-primary"
                        ),
                        class_="card-body"
                    ),
                    class_="card mb-3 shadow-sm"
                )
            )
        
        return ui.div(
            ui.h4("📰 Noticias Relevantes", class_="mb-3"),
            *news_cards,
            class_="p-3"
        )
         
    @output
    @render.download(filename=lambda: f"{selected_player_data().get('nombre', 'informe')}_informe.pdf",
                 media_type="application/pdf")
    def download_pdf():
        player = selected_player_data()
        if not player:
            return None  # o lanzar un error manejado
        
        filename = f"/tmp/{player['nombre'].replace(' ', '_')}_informe.pdf"
        generar_pdf(player, filename)
        ui.notification_show("Descarga iniciada. Si no se descarga automáticamente, revise su navegador.", 
                         type="message", duration=5)
        return filename
    
    @output
    @render.ui
    def player_achievements_ui():
        player = selected_player_data()
        if not player or 'logros' not in player or not player['logros']:
            return ui.div(
                ui.h4("🏆 Logros del Jugador", class_="mb-3"),
                ui.div("No hay información de logros disponible", class_="alert alert-warning"),
                class_="p-3"
            )
        
        achievements = player['logros']
        df = pd.DataFrame(achievements)
        
        # Agrupar logros por categoría para mejor visualización
        grouped = df.groupby('Categoría')
        
        achievement_cards = []
        for category, group in grouped:
            items = [
                ui.tags.li(
                    ui.div(
                        ui.span(f"🏅 {row['Temporada']}", class_="fw-bold me-2"),
                        ui.span(f"({row['Club']})", class_="text-muted"),
                        class_="d-flex justify-content-between"
                    ),
                    class_="list-group-item border-0 py-2"
                )
                for _, row in group.iterrows()
            ]
            
            achievement_cards.append(
                ui.div(
                    ui.div(
                        ui.h5(category, class_="card-title text-primary"),
                        ui.tags.ul(*items, class_="list-group list-group-flush"),
                        class_="card-body"
                    ),
                    class_="card mb-3 shadow-sm"
                )
            )
        
        return ui.div(
            ui.h4("🏆 Logros del Jugador", class_="mb-3"),
            ui.div(
                ui.output_data_frame("achievements_table"),
                class_="mb-4"
            ),
            ui.h5("Resumen por Categoría", class_="mb-3"),
            *achievement_cards,
            class_="p-3"
        )
    
    @output
    @render.data_frame
    def achievements_table():
        player = selected_player_data()
        if not player or 'logros' not in player:
            return render.DataGrid(pd.DataFrame({"Mensaje": ["No hay datos de logros disponibles"]}))
        
        df = pd.DataFrame(player['logros'])
        return render.DataGrid(
            df,
            filters=False,
            width="100%",
            height="300px"
        )
    
    @output
    @render.data_frame
    def tm_injuries_table():
        player = selected_player_data()
        if not player or 'lesiones' not in player:
            return "No hay historial de lesiones disponible"
        
        df = pd.DataFrame(player['lesiones'])
        return render.DataGrid(df, width="100%")
    
    @reactive.effect
    @reactive.event(input.tm_get_details)
    async def _get_player_media():
        """Obtiene detalles del jugador incluyendo noticias y videos"""
        selected_row = input.tm_results_table_selected_rows()
        if not selected_row:
            return
        
        player = tm_results()[selected_row[0]]
        
        with ui.Progress(min=0, max=1) as p:
            p.set(message="Obteniendo detalles del jugador...")
            
            # Ejecutar todas las búsquedas en paralelo
            details_task = asyncio.to_thread(sync_scrape_player_info, player['Enlace'])
            image_task = asyncio.to_thread(google_image_search, player['Nombre'], player.get('Club'))
            club_image_task = asyncio.to_thread(google_club_image_search, player.get('Club'))
            stats_task = asyncio.to_thread(get_player_stats, player['Enlace'].split('/')[-1])
            achievements_task = asyncio.to_thread(get_player_achievements, player['Enlace'].split('/')[-1])
            news_task = asyncio.to_thread(buscar_noticias_deportivas, player['Nombre'], player.get('Club'))
            videos_task = asyncio.to_thread(buscar_highlights_youtube, player['Nombre'], player.get('Club'))
            
            details, image_url, club_image_url, stats_df, achievements_df, news, videos = await asyncio.gather(
                details_task, image_task, club_image_task, stats_task, achievements_task, news_task, videos_task
            )
            
            details['nombre'] = player['Nombre']
            details['imagen_url'] = image_url
            details['club_imagen_url'] = club_image_url
            details['logros'] = achievements_df.to_dict('records') if not achievements_df.empty else []
            selected_player_data.set(details)
            player_news.set(news if news else [])
            player_videos.set(videos if videos else [])
            

    # Añadimos una nueva función para mostrar lesiones en su propia pestaña
    @output
    @render.ui
    def player_injuries_ui():
        player = selected_player_data()
        if not player or 'lesiones' not in player or not player['lesiones']:
            return ui.div(
                ui.h4("🤕 Historial de Lesiones", class_="mb-3"),
                ui.div("No hay historial de lesiones disponible", class_="alert alert-warning"),
                class_="p-3"
            )
        
        injuries = player['lesiones']
        
        # Creamos una tabla con estilo mejorado
        return ui.div(
            ui.h4("🤕 Historial de Lesiones", class_="mb-3"),
            ui.div(
                ui.output_data_frame("tm_injuries_table"),
                class_="border rounded p-3 bg-light"
            ),
            ui.div(
                ui.h5("Resumen de Lesiones", class_="mt-4"),
                ui.markdown(f"""
                - **Total de lesiones registradas:** {len(injuries)}
                - **Última lesión:** {injuries[0]['Tipo'] if injuries else 'N/A'}
                - **Partidos totales perdidos:** {sum(int(lesion['Partidos_Perdidos']) for lesion in injuries if 'Partidos_Perdidos' in lesion and lesion['Partidos_Perdidos'].isdigit())}
                """),
                class_="p-3 bg-white border rounded mt-3"
            ),
            class_="p-3"
        )
        
    @output
    @render.ui
    def player_videos_ui():
        videos = player_videos()
        if not videos:
            return ui.div(
                ui.h4(ui.HTML('<i class="fa-solid fa-video me-2"></i> Highlights')),
                ui.div("No se encontraron videos recientes", class_="alert alert-warning"),
                class_="p-3"
            )
        
        video_cards = []
        for video in videos:
            video_cards.append(
                ui.div(
                    ui.div(
                        ui.h5(video['titulo'], class_="card-title"),
                        ui.p(
                            ui.span(video['canal'], class_="text-muted me-2"),
                            ui.span("•", class_="text-muted mx-1"),
                            ui.span(video['fecha'], class_="text-muted")
                        ),
                        ui.div(
                            ui.tags.iframe(
                                src=f"https://www.youtube.com/embed/{video['id']}",
                                width="100%",
                                height="315",
                                frameborder="0",
                                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture",
                                allowfullscreen=True,
                                style="border-radius: 8px;"
                            ),
                            class_="ratio ratio-16x9 mb-3"
                        ),
                        ui.a(
                            "Ver en YouTube",
                            href=f"https://youtube.com/watch?v={video['id']}",
                            target="_blank",
                            class_="btn btn-danger btn-sm"
                        ),
                        class_="card-body"
                    ),
                    class_="card mb-4 shadow-sm"
                )
            )
            
        ui.notification_show("Detalles obtenidos con éxito", type="message", duration=3)
        
        return ui.div(
            ui.h4(ui.HTML('<i class="fa-solid fa-video me-2"></i> Últimos Highlights')),
            *video_cards,
            class_="p-3"
        )

#######
####3 pagina 3
####
    # Estado reactivo para datos del entrenador
    coach_data = reactive.Value(None)
    coach_image_url = reactive.Value(None)
    coach_history = reactive.Value(pd.DataFrame())
    coach_achievements = reactive.Value(pd.DataFrame())

    @reactive.effect
    @reactive.event(input.buscar_entrenador)
    async def _search_coach():
        """Busca información del entrenador"""
        nombre = input.nombre_entrenador()
        if not nombre:
            ui.notification_show("Por favor ingrese un nombre", type="error")
            return

        with ui.Progress(min=0, max=1) as p:
            p.set(message="Buscando entrenador...")

            # Obtener URL del perfil
            profile_url = await asyncio.to_thread(get_coach_profile_url, nombre)
            
            if not profile_url or isinstance(profile_url, str) and 'Error' in profile_url:
                error_msg = profile_url or "No se encontró el perfil del entrenador"
                coach_data.set({"Error": error_msg})
                ui.notification_show(error_msg, type="error")
                return

            # Obtener datos del perfil
            profile_data = await asyncio.to_thread(scrape_coach_profile_from_url, profile_url)
            
            if 'Error' in profile_data:
                coach_data.set(profile_data)
                ui.notification_show(profile_data['Error'], type="error")
                return

            # Obtener imagen del entrenador
            image_url = await asyncio.to_thread(
                google_coach_image_search, 
                f"{nombre} entrenador"
            )

            # Obtener historial y logros si hay ID disponible
            if 'coach_id' in profile_data:
                try:
                    # Obtener historial de clubes
                    name_slug = profile_url.split('/')[-3]  # Extraer slug del nombre de la URL
                    history_df, _ = await asyncio.to_thread(
                        get_coach_club_history,
                        name_slug,
                        profile_data['coach_id']
                    )
                    coach_history.set(history_df)
                    
                    # Obtener logros
                    achievements_df = await asyncio.to_thread(
                        get_coach_achievements,
                        profile_data['coach_id']
                    )
                    coach_achievements.set(achievements_df)
                    
                except Exception as e:
                    print(f"Error obteniendo datos adicionales: {str(e)}")

            # Actualizar estados reactivos
            coach_data.set(profile_data)
            coach_image_url.set(image_url)
            ui.notification_show("Información del entrenador obtenida", type="message", duration=3)

    @output
    @render.ui
    def coach_header():
        """Cabecera con foto e información básica"""
        data = coach_data()
        if not data or 'Error' in data:
            return ui.div(
                ui.h4("Introduce un nombre de entrenador y haz clic en Buscar", class_="text-muted text-center mt-5"),
                class_="alert alert-info"
            )

        return ui.div(
            ui.layout_columns(
                # Imagen del entrenador
                ui.div(
                    ui.img(
                        src=coach_image_url() or "https://via.placeholder.com/300x350?text=No+Image",
                        style="width: 100%; max-height: 300px; object-fit: cover;",
                        class_="img-thumbnail mb-3"
                    ),
                    class_="text-center",
                    width=3
                ),
                # Información básica
                ui.div(
                    ui.h2(data.get('nombre_completo', 'Nombre no disponible'), class_="mb-3"),
                    ui.div(
                        ui.span(f"📅 {data.get('fecha_nacimiento', 'N/A')}", 
                               class_="badge bg-light text-dark me-2 mb-2"),
                        ui.span(f"🌍 {', '.join(data.get('nacionalidades', ['N/A']))}", 
                               class_="badge bg-light text-dark me-2 mb-2"),
                        ui.span(f"📏 {data.get('media_tiempo_entrenador', 'N/A')} avg", 
                               class_="badge bg-light text-dark me-2 mb-2"),
                        ui.span(f"📝 {data.get('licencia', 'N/A')}", 
                               class_="badge bg-light text-dark me-2 mb-2"),
                        class_="mb-3"
                    ),
                    width=9
                ),
                class_="mb-4 align-items-center"
            ),
            class_="bg-light p-4 rounded-3 mb-4"
        )

    @output
    @render.ui
    def coach_basic_info():
        """Muestra la información básica del entrenador"""
        data = coach_data()
        if not data or 'Error' in data:
            return None

        def info_row(label, value, icon):
            return ui.div(
                ui.div(icon, class_="col-1 text-end pe-3"),
                ui.div(ui.strong(label), class_="col-3"),
                ui.div(value or 'N/A', class_="col-8"),
                class_="row mb-2"
            )

        return ui.div(
            ui.h4("📋 Información Personal", class_="mb-3"),
            info_row("Nombre completo:", data.get('nombre_completo'), "👤"),
            info_row("Fecha nacimiento:", data.get('fecha_nacimiento'), "🎂"),
            info_row("Lugar nacimiento:", data.get('lugar_nacimiento'), "📍"),
            info_row("Nacionalidad:", ', '.join(data.get('nacionalidades', ['N/A'])), "🌍"),

            ui.hr(),

            ui.h4("⚽ Estilo de Juego", class_="mb-3"),
            info_row("Formación preferida:", data.get('formacion_preferida'), "📊"),
            info_row("Licencia:", data.get('licencia'), "📜"),
            info_row("Agente:", data.get('agente'), "👔"),

            class_="p-3 bg-light rounded-3"
        )

    @output
    @render.ui
    def coach_club_history_display():
        history = coach_history()
        if history.empty:
            return ui.div(
                ui.h4("No hay historial de clubes disponible", class_="text-muted text-center mt-5")
            )

        return ui.div(
            ui.h3("📚 Historial de Clubes", class_="mb-4"),
            ui.output_data_frame("coach_history_table"),
            class_="p-3"
        )

    @output
    @render.data_frame
    def coach_history_table():
        return render.DataGrid(coach_history(), width="100%")

    @output
    @render.ui
    def coach_achievements_display():
        achievements = coach_achievements()
        if achievements.empty:
            return ui.div(
                ui.h4("No hay información de logros disponible", class_="text-muted text-center"),
                class_="mt-5"
            )

        # Agrupar logros por tipo
        grouped = achievements.groupby('Logro')
        cards = []

        for achievement_type, group in grouped:
            items = [
                ui.tags.li(f"{row['Temporada']} - {row['Competición']}", 
                          class_="list-group-item border-0 py-1")
                for _, row in group.iterrows()
            ]

            cards.append(
                ui.div(
                    ui.div(
                        ui.h5(achievement_type, class_="card-title"),
                        ui.tags.ul(*items, class_="list-group list-group-flush"),
                        class_="card-body"
                    ),
                    class_="card mb-3 shadow-sm"
                )
            )

        return ui.div(
            ui.h3("🏆 Historial de Logros", class_="mb-4"),
            *cards,
            class_="p-3"
        )
        
    @output
    @render.download(filename=lambda: f"{coach_data().get('nombre_completo', 'entrenador').replace(' ', '_')}_informe.pdf")
    def download_coach_pdf():
        data = coach_data()
        if not data or 'Error' in data:
            return None
            
        # Crear archivo temporal
        temp_dir = tempfile.mkdtemp()
        filename = os.path.join(temp_dir, f"{data.get('nombre_completo', 'entrenador').replace(' ', '_')}_informe.pdf")
        
        # Generar PDF
        generar_pdf_entrenador(
            data,
            coach_history(),
            coach_achievements(),
            filename
        )
        
        # Notificación
        ui.notification_show(
            f"Informe de {data.get('nombre_completo', 'el entrenador')} generado con éxito",
            type="message",
            duration=5
        )
        
        return filename
  ## --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------  --------------          
    ## --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------  --------------        
    ## --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------  --------------    

    # 1. Actualización del selector de temporada para el análisis de radar
    @reactive.Effect
    @reactive.event(input.tm_player_select)
    def update_tm_season_choices():
        """Actualiza las opciones de temporada basado en el jugador seleccionado en Transfermarkt"""
        player = input.tm_player_select()
        
        if not player or not isinstance(df2, pd.DataFrame) or df2.empty:
            ui.update_select("season", choices=["No disponible"], selected="No disponible")
            return
        
        try:
            # Filtramos las temporadas disponibles para el jugador
            player_data = df2[df2['playerName'] == player]
            
            if player_data.empty:
                ui.update_select("season", choices=["No disponible"], selected="No disponible")
                return
                
            # Obtenemos temporadas únicas y ordenadas (más reciente primero)
            seasons = sorted(player_data['season'].unique().tolist(), reverse=True)
            
            if not seasons:
                ui.update_select("season", choices=["No disponible"], selected="No disponible")
                return
                
            # Preparamos las opciones
            choices = ["Todas"] + seasons
            selected = seasons[0]  # Selecciona la temporada más reciente por defecto
            
            ui.update_select(
                "season",  # Asegurarse que coincide con el ID del input
                choices=choices,
                selected=selected
            )
            
        except Exception as e:
            print(f"Error actualizando temporadas: {str(e)}")
            ui.update_select("season", choices=["Error cargando datos"], selected="Error cargando datos")

    # 2. Modificar la función all_radar_plots para usar el selector correcto
    @output
    @render.ui
    @reactive.event(input.tm_player_select, input.season)  # Usar input.season aquí
    def all_radar_plots():
        player = input.tm_player_select()
        season = input.season()  # Usar el selector correcto
        
        if not player or df2.empty or season in ["No disponible", "Error cargando datos"]:
            return ui.div("Selecciona un jugador para ver los gráficos.", 
                        class_="text-center mt-5 text-muted")
        
        # Si se selecciona "Todas", no filtrar por temporada
        if season == "Todas":
            season_filter = None
        else:
            season_filter = season

        cards = []
        for group_name in groups:
            safe_id = group_name.lower().replace(" ", "_")
            widget_id = f"tm_radar_{safe_id}"

            # Verificar si la temporada existe para este jugador
            if season_filter and season_filter != "Todas":
                player_seasons = df2[df2['playerName'] == player]['season'].unique()
                if season_filter not in player_seasons:
                    continue

            cards.append(
                ui.div(
                    ui.div(
                        ui.div(
                            ui.h5(group_name, class_="mb-0"),
                            class_="card-header text-center"
                        ),
                        ui.div(
                            output_widget(widget_id),
                            class_="p-3"
                        ),
                        class_="card-radar"
                    ),
                    class_="grid-item"
                )
            )

            # Necesitamos una copia local del valor actual
            current_group = group_name

            @output(id=widget_id)
            @render_widget
            def _(group=current_group):
                return generate_radar_plot(df2.copy(), player, group, season_filter)

        return ui.div(
            ui.hr(),
            ui.h4("Análisis por Dimensiones", class_="mb-4 mt-4"),
            ui.div(
                *cards,
                class_="grid-container"
            )
        )

    # 3. Función para obtener datos del jugador para el análisis de radar
    @reactive.Calc
    def tm_radar_player_data():
        """Obtiene los datos del jugador para el análisis de radar"""
        player = input.tm_player_select()
        season = input.tm_season()
        
        # Validaciones básicas
        if (not player or not isinstance(df2, pd.DataFrame) or df2.empty or 
           season in ["No disponible", "Error cargando datos"]):
            return None
            
        try:
            # Filtramos por jugador
            player_df = df2[df2['playerName'] == player]
            
            # Si se seleccionó una temporada específica (no "Todas")
            if season and season != "Todas las temporadas":
                player_df = player_df[player_df['season'] == season]
                
            if player_df.empty:
                return None
                
            # Obtenemos el registro más reciente si hay múltiples
            player_df = player_df.sort_values('season', ascending=False)
            return player_df.iloc[0].to_dict()
            
        except Exception as e:
            print(f"Error obteniendo datos del jugador: {str(e)}")
            return None

    # 4. Actualizamos las funciones de visualización del radar para usar tm_radar_player_data()
    @output
    @render.ui
    def tm_player_header():
        stats = tm_radar_player_data()
        if not stats:
            return ui.div(
                ui.h4("Selecciona un jugador para comenzar el análisis", class_="text-muted"),
                class_="player-header text-center"
            )
        
        return ui.div(
            ui.div(
                ui.h2(stats['playerName'], class_="mb-2"),
                ui.h4(f"{stats.get('positions', 'N/A')} | {stats.get('squadName', 'N/A')}", 
                     class_="text-muted mb-3"),
                ui.div(
                    ui.span(f"📅 {stats.get('birthdate', 'N/A')}", class_="me-3"),
                    ui.span(f"🌍 {stats.get('birthplace', 'N/A')}", class_="me-3"),
                    ui.span(f"🦶 {stats.get('leg', 'N/A')}"),
                    class_="mb-3 text-secondary"
                ),
                ui.div(
                    ui.span(f"📊 IMPECT Score: {stats.get('IMPECT_SCORE_PACKING', 0):.2f}", 
                        class_="badge-stat bg-primary"),
                    ui.span(f"⚽ Ofensivo: {stats.get('OFFENSIVE_IMPECT_SCORE_PACKING', 0):.2f}", 
                        class_="badge-stat bg-success"),
                    ui.span(f"🛡️ Defensivo: {stats.get('DEFENSIVE_IMPECT_SCORE_PACKING', 0):.2f}", 
                        class_="badge-stat bg-danger"),
                    ui.span(f"📈 Progresión: {stats.get('PROGRESSION_SCORE_PACKING', 0):.2f}", 
                        class_="badge-stat bg-info"),
                    ui.span(f"🎯 Recepción: {stats.get('RECEIVING_SCORE_PACKING', 0):.2f}", 
                        class_="badge-stat bg-warning text-dark"),
                ),
                class_="text-center"
            ),
            class_="player-header"
        )

       
    ## --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------  --------------          
    ## --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------  --------------        
    ## --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------  --------------       
    ### 5
    # Variables reactivas
    player_seasons = reactive.Value({})
    available_leagues = reactive.Value([])
    available_teams = reactive.Value([])
    
    # Añade este efecto reactivo en el servidor:
    @reactive.Effect
    def handle_select_all_buttons():
        categories = metric_categories.get()
        for category in categories:
            category_id = category.lower().replace(" ", "_")
            
            if input[f"select_all_{category_id}"]():
                for metric in categories[category]:
                    ui.update_checkbox(f"metric_{metric}", value=True)
            
            if input[f"deselect_all_{category_id}"]():
                for metric in categories[category]:
                    ui.update_checkbox(f"metric_{metric}", value=False)
                    
    # Actualizar opciones de jugadores
    @reactive.Effect
    def _():
        players = df2['playerName'].unique().tolist()
        ui.update_selectize("players", choices=players)
        
    # Selectores de temporada para cada jugador
    @render.ui
    def player_season_selectors():
        players = input.players()
        if not players:
            return None
        
        season_selectors = []
        for player in players:
            available_seasons = df2[df2['playerName'] == player]['season'].unique().tolist()
            season_id = f"season_{player.replace(' ', '_')}"
            season_selectors.append(
                ui.div(
                    ui.input_select(
                        season_id,
                        f"Temporada para {player}",
                        choices=available_seasons,
                        selected=available_seasons[0] if available_seasons else None,
                        width="100%"
                    ),
                    class_="season-selector-card animated"
                )
            )
        
        # Contenedor para los selectores de temporada
        return ui.div(
            ui.h4("Selección de Temporadas", class_="card-title"),
            ui.div(
                *season_selectors,
                class_="season-selectors-container"
            ),
            class_="mt-3"
        )

    # Actualizar temporadas seleccionadas
    @reactive.Effect
    def update_player_seasons():
        players = input.players()
        current = {}
        for player in players:
            season_id = f"season_{player.replace(' ', '_')}"
            current[player] = input[season_id]()
        player_seasons.set(current)
    
    # Categorías de métricas
    metric_categories = reactive.Value({
        'Impacto Ofensivo': [
            'IMPECT_SCORE_PACKING',
            'IMPECT_SCORE_WITHOUT_GOALS_PACKING',
            'IMPECT_SCORE_WITH_POSTSHOT_XG_PACKING',
            'SCORER_SCORE',
            'PROGRESSION_SCORE_PACKING',
            'OFFENSIVE_IMPECT_SCORE_PACKING',
            'OFFENSIVE_IMPECT_SCORE_WITHOUT_GOALS_PACKING',
            'OFFENSIVE_IMPECT_SCORE_WITH_POSTSHOT_XG_PACKING'
        ],
        'Impacto Defensivo': [
            'INTERVENTIONS_SCORE_PACKING',
            'DEFENSIVE_POSITIONAL_PLAY_SCORE_PACKING',
            'DEFENSIVE_IMPECT_SCORE_PACKING',
            'ADDED_OPPONENTS_WITHOUT_SHOTS_AT_GOAL',
            'LOOSE_BALL_REGAIN_SCORE',
            'INTERCEPTION_SCORE',
            'BLOCK_SCORE'
        ],
        'Posesión y Progresión': [
            'RECEIVING_SCORE_PACKING',
            'LOW_PASS_SCORE',
            'LOW_CROSS_SCORE',
            'HIGH_CROSS_SCORE',
            'DIAGONAL_PASS_SCORE',
            'CHIPPED_PASS_SCORE',
            'SHORT_AERIAL_PASS_SCORE',
            'DRIBBLE_SCORE',
            'AVAILABILITY_OUT_WIDE_SCORE',
            'AVAILABILITY_BTL_SCORE',
            'AVAILABILITY_FDR_SCORE',
            'AVAILABILITY_IN_THE_BOX_SCORE'
        ],
        'Zonas de Packing': [
            'TOTAL_TOUCHES_IN_PACKING_ZONE_FBR',
            'TOTAL_TOUCHES_IN_PACKING_ZONE_CB',
            'TOTAL_TOUCHES_IN_PACKING_ZONE_FBL',
            'TOTAL_TOUCHES_IN_PACKING_ZONE_DM',
            'TOTAL_TOUCHES_IN_PACKING_ZONE_WR',
            'TOTAL_TOUCHES_IN_PACKING_ZONE_WL',
            'TOTAL_TOUCHES_IN_PACKING_ZONE_CM',
            'TOTAL_TOUCHES_IN_PACKING_ZONE_AM',
            'TOTAL_TOUCHES_IN_PACKING_ZONE_IBWR',
            'TOTAL_TOUCHES_IN_PACKING_ZONE_IBWL',
            'TOTAL_TOUCHES_IN_PACKING_ZONE_IB',
            'AERIAL_DUELS_NUMBER_IN_PACKING_ZONE_CB'
        ],
        'Finalización': [
            'LONG_RANGE_SHOT_SCORE',
            'MID_RANGE_SHOT_SCORE',
            'CLOSE_RANGE_SHOT_SCORE',
            'ONE_VS_ONE_AGAINST_GK_SCORE',
            'OPEN_GOAL_SHOT_SCORE',
            'HEADER_SHOT_SCORE',
            'OFFENSIVE_HEADER_SCORE'
        ],
        'Acciones Defensivas': [
            'DEFENSIVE_HEADER_SCORE',
            'CLEARANCE_SCORE',
            'GROUND_DUEL_SCORE',
            'RATIO_AERIAL_DUELS',
            'AERIAL_DUELS_NUMBER',
            'RATIO_GROUND_DUELS'
        ],
        'Acciones Estratégicas': [
            'THROW_IN_SCORE',
            'CORNER_SCORE',
            'FREE_KICK_SCORE',
            'PENALTY_SCORE',
            'GOAL_KICK_SCORE'
        ],
        'Ratios y Eficiencia': [
            'RATIO_REMOVED_OPPONENTS',
            'RATIO_REMOVED_OPPONENTS_DEFENDERS',
            'RATIO_ADDED_TEAMMATES',
            'RATIO_ADDED_TEAMMATES_DEFENDERS',
            'RATIO_MINUTES_PER_GOAL',
            'RATIO_MINUTES_PER_SHOT_XG',
            'RATIO_GOALS_SHOT_XG',
            'RATIO_SHOTS_ON_TARGET',
            'RATIO_SHOTS_PER_GOAL',
            'RATIO_MINUTES_PER_ASSIST',
            'RATIO_PASSING_ACCURACY',
            'RATIO_POSTSHOT_XG_SHOT_XG',
            'RATIO_GOALS_POSTSHOT_XG'
        ],
        'Porteros': [
            'GK_PREVENTED_GOALS_TOTAL_POSTSHOT_XG',
            'GK_PREVENTED_GOALS_TOTAL_POSTSHOT_XG_PERCENT',
            'GK_PREVENTED_GOALS_TOTAL_SHOT_XG',
            'GK_PREVENTED_GOALS_TOTAL_SHOT_XG_PERCENT',
            'GK_DEFENSIVE_TOUCHES_OUTSIDE_OWN_BOX',
            'GK_CAUGHT_HIGH_BALLS_PERCENT',
            'GK_CAUGHT_AND_PUNCHED_HIGH_BALLS_PERCENT',
            'GK_SUCCESSFUL_LAUNCHES_PERCENT'
        ],
        'Otras Métricas': [
            'TOTAL_TOUCHES',
            'NUMBER_OF_GROUND_DUELS',
            'SUCCESSFUL_PASSES_CLEAN',
            'UNSUCCESSFUL_PASSES_CLEAN',
            'HOLD_UP_PLAY_SCORE',
            'DEVIATION_BYPASSED_DEFENDERS',
            'SUFFERED_BYPASSED_OPPONENTS',
            'DEVIATION_CHANCES',
            'RATIO_ADDED_OPPONENTS',
            'RATIO_REVERSE_PLAY_ADDED_OPPONENTS'
        ]
    })

    @render.ui
    def dynamic_metric_selector():
        categories = metric_categories.get()
        metric_elements = []
        
        for category, metrics in categories.items():
            category_id = category.lower().replace(" ", "_")
            metric_elements.append(
                ui.div(
                    ui.div(
                        ui.div(
                            ui.span(category, class_="metric-category-title"),
                            ui.span(
                                ui.HTML('<i class="fas fa-chevron-down"></i>'),
                                id=f"icon_{category_id}"
                            ),
                            style="display: flex; justify-content: space-between; align-items: center;"
                        ),
                        onclick=f"toggleCategory('{category_id}')",
                        class_="metric-category-header"
                    ),
                    ui.div(
                        ui.div(
                            ui.input_action_button(
                                    f"select_all_{category_id}",
                                    "Seleccionar todos",
                                    class_="btn btn-sm btn-outline-primary mb-2 mr-2"
                                ),
                                ui.input_action_button(
                                f"deselect_all_{category_id}",
                                "Deseleccionar todos",
                                class_="btn btn-sm btn-outline-secondary mb-2"
                            ),
                            class_="mb-2"
                        ),
                        ui.div(
                            *[
                                ui.div(
                                    ui.input_checkbox(
                                        f"metric_{metric}",
                                        metric,
                                        value=False
                                    ),
                                    class_="metric-item"
                                )
                                for metric in metrics
                            ],
                            class_="metric-items",
                            id=f"metrics_{category_id}"
                        ),
                        class_="metric-category-content",
                        id=f"content_{category_id}"
                    ),
                    class_="metric-category",
                    id=f"category_{category_id}"
                )
            )
        
        return ui.TagList(
            ui.tags.script("""
                function toggleCategory(categoryId) {
                    const content = document.getElementById(`content_${categoryId}`);
                    const icon = document.getElementById(`icon_${categoryId}`);
                    
                    if (content.style.display === 'none') {
                        content.style.display = 'block';
                        icon.innerHTML = '<i class="fas fa-chevron-up"></i>';
                    } else {
                        content.style.display = 'none';
                        icon.innerHTML = '<i class="fas fa-chevron-down"></i>';
                    }
                }
                
                function selectAllMetrics(categoryId, select) {
                    const checkboxes = document.querySelectorAll(`#metrics_${categoryId} input[type="checkbox"]`);
                    checkboxes.forEach(checkbox => {
                        checkbox.checked = select;
                        // Trigger Shiny input change
                        $(checkbox).trigger('change');
                    });
                }
                
                // Initialize all categories as collapsed
                document.querySelectorAll('.metric-category-content').forEach(el => {
                    el.style.display = 'none';
                });
            """),
            *metric_elements
        )

    # Tabla comparativa profesional
    @render.ui
    def comparison_table():
        players = input.players()
        metrics = selected_metrics()
        group_type = input.comparison_group()
        
        if not players or not metrics:
            return ui.div(
                    "Por favor selecciona al menos un jugador y algunas métricas para generar la tabla comparativa.",
                    class_="alert alert-info my-4",
                    role="alert"
            )
        
        # Obtener temporada de referencia
        ref_season = player_seasons.get().get(players[0]) if players else None
        
        # Construir dataframe con los datos
        table_data = []
        for metric in metrics:
            row = {"Métrica": ui.span(metric, class_="highlight-cell")}
            
            # Valores de los jugadores
            for player in players:
                season = player_seasons.get().get(player)
                player_data = df2[(df2['playerName'] == player) & (df2['season'] == season)]
                
                if not player_data.empty and metric in player_data.columns:
                    value = player_data[metric].iloc[0] if len(player_data) > 0 else None
                    if value is not None:
                        row[player] = f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
                    else:
                        row[player] = ui.span("N/D", style="color: #94a3b8;")
                else:
                    row[player] = ui.span("N/D", style="color: #94a3b8;")
            
            # Añadir grupo de comparación si corresponde
            if group_type in ["liga", "equipo"] and ref_season:
                if group_type == "liga" and input.selected_league_compare():
                    league = input.selected_league_compare()
                    league_players = df2[(df2['competitionName'] == league) & 
                                      (df2['season'] == ref_season)]
                    
                    if not league_players.empty and metric in league_players.columns:
                        avg = league_players[metric].mean()
                        row[f"Promedio {league}"] = ui.span(
                            f"{avg:.2f}",
                            class_="comparison-badge"
                        )
                
                elif group_type == "equipo" and input.selected_team_compare():
                    team = input.selected_team_compare()
                    team_players = df2[(df2['squadName'] == team) & 
                                    (df2['season'] == ref_season)]
                    
                    if not team_players.empty and metric in team_players.columns:
                        avg = team_players[metric].mean()
                        row[f"Promedio {team}"] = ui.span(
                            f"{avg:.2f}",
                            class_="comparison-badge"
                        )
            
            table_data.append(row)
        
        # Convertir a DataFrame
        df_table = pd.DataFrame(table_data)
        
        # Renderizar tabla profesional con estilo
        return ui.HTML(
            df_table.to_html(
                classes="data-table",
                escape=False,
                index=False,
                border=0
            )
        )

    # Obtener métricas seleccionadas
    @reactive.Calc
    def selected_metrics():
        categories = metric_categories.get()
        return [metric for metrics in categories.values() 
                for metric in metrics if input[f"metric_{metric}"]()]

    # Actualizar datos de comparación (ligas/equipos disponibles)
    @reactive.Effect
    def update_comparison_data():
        players = input.players()
        if not players:
            available_leagues.set([])
            available_teams.set([])
            return
        
        players_data = df2[df2['playerName'].isin(players)]
        available_leagues.set(players_data['competitionName'].unique().tolist())
        available_teams.set(players_data['squadName'].unique().tolist())

    # Selector de liga/equipo para comparación
    # In your comparison_selector function, make sure the input IDs are unique
    @render.ui
    def comparison_selector():
        if input.comparison_group() == "liga":
            return ui.div(
                ui.input_select(
                    "selected_league_compare",  # Changed ID to be unique
                    "Selecciona liga para comparar",
                    choices=available_leagues.get(),
                    width="100%"
                ),
                class_="mt-2"
            )
        elif input.comparison_group() == "equipo":
            return ui.div(
                ui.input_select(
                    "selected_team_compare",  # Changed ID to be unique
                    "Selecciona equipo para comparar",
                    choices=available_teams.get(),
                    width="100%"
                ),
                class_="mt-2"
            )
        return None

    # Gráfico radar mejorado
    @render_widget
    def radar_chart_widget():
        players = input.players()
        metrics = selected_metrics()
        group_type = input.comparison_group()
        
        if not players or not metrics:
            fig = go.Figure()
            fig.update_layout(
                title="Selecciona jugadores y métricas para generar el gráfico",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color="#333")
            )
            return fig
        
        # Obtener temporada de referencia
        ref_season = player_seasons.get().get(players[0]) if players else None
        
        # Obtener posición común si existe
        positions = {df2[df2['playerName'] == player]['positions'].iloc[0] for player in players if not df2[df2['playerName'] == player].empty}
        common_position = positions.pop() if len(positions) == 1 else None
        
        # Preparar datos de jugadores
        traces = []
        colors = px.colors.qualitative.Plotly
        
        for i, player in enumerate(players):
            season = player_seasons.get().get(player)
            player_data = df2[(df2['playerName'] == player) & (df2['season'] == season)]
            
            if player_data.empty:
                continue
                
            player_data = player_data.iloc[0]
            
            values = []
            for metric in metrics:
                if metric in player_data:
                    # Normalizar basado en todos los jugadores de la misma posición
                    if common_position:
                        pos_players = df2[df2['positions'] == common_position]
                        metric_values = pos_players[metric].dropna()
                    else:
                        metric_values = df2[metric].dropna()
                    
                    if len(metric_values) > 0:
                        low, high = np.percentile(metric_values, [5, 95])
                        val = player_data[metric]
                        norm_value = (val - low) / (high - low) if (high - low) != 0 else 0.5
                        values.append(np.clip(norm_value, 0, 1))
                    else:
                        values.append(0.5)
                else:
                    values.append(0)
            
            traces.append(go.Scatterpolar(
                r=values + [values[0]],
                theta=metrics + [metrics[0]],
                fill='toself',
                name=f"{player} ({season})",
                line=dict(color=colors[i % len(colors)], width=2),
                opacity=0.8,
                hovertemplate="<b>%{theta}</b><br>Valor: %{r:.2f}<extra></extra>"
            ))
            
        # Añadir grupo de comparación si corresponde
        if group_type in ["liga", "equipo"] and players and ref_season:
            if group_type == "liga" and input.selected_league_compare():
                group_name = f"Promedio {input.selected_league_compare()} ({ref_season})"
                group_df = df2[(df2['competitionName'] == input.selected_league_compare()) & 
                             (df2['season'] == ref_season)]
            elif group_type == "equipo" and input.selected_team_compare():
                group_name = f"Promedio {input.selected_team_compare()} ({ref_season})"
                group_df = df2[(df2['squadName'] == input.selected_team_compare()) & 
                           (df2['season'] == ref_season)]
            else:
                group_df = pd.DataFrame()
            
            # Filtrar por posición si hay una común
            if common_position and not group_df.empty:
                group_df = group_df[group_df['positions'] == common_position]
            
            if not group_df.empty:
                group_values = []
                for metric in metrics:
                    if metric in group_df.columns:
                        metric_values = group_df[metric].dropna()
                        if len(metric_values) > 0:
                            avg = metric_values.mean()
                            # Usar mismos percentiles que para los jugadores
                            if common_position:
                                pos_players = df2[df2['positions'] == common_position]
                                metric_range = pos_players[metric].dropna()
                            else:
                                metric_range = df2[metric].dropna()
                            
                            if len(metric_range) > 0:
                                low, high = np.percentile(metric_range, [5, 95])
                                norm_value = (avg - low) / (high - low) if (high - low) != 0 else 0.5
                                group_values.append(np.clip(norm_value, 0, 1))
                            else:
                                group_values.append(0.5)
                        else:
                            group_values.append(0.5)
                    else:
                        group_values.append(0)
                
                traces.append(go.Scatterpolar(
                    r=group_values + [group_values[0]],
                    theta=metrics + [metrics[0]],
                    fill='toself',
                    name=group_name,
                    line=dict(color='#7f8c8d', width=2, dash='dot'),
                    opacity=0.4,
                    hovertemplate="<b>%{theta}</b><br>Valor promedio: %{r:.2f}<extra></extra>"
                ))
        
        # Configuración final del gráfico
        fig = go.Figure(data=traces)
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 1],
                    tickvals=[0, 0.5, 1],
                    ticktext=['Percentil 5', 'Mediana', 'Percentil 95'],
                    gridcolor='#e2e8f0',
                    linecolor='#e2e8f0',
                    tickfont=dict(color='#64748b')
                ),
                angularaxis=dict(
                    gridcolor='#e2e8f0',
                    linecolor='#e2e8f0',
                    tickfont=dict(color='#64748b')
                ),
                bgcolor='rgba(0,0,0,0)'
            ),
            height=500,
            width=800,
            margin=dict(l=80, r=80, t=80, b=200),  # Aumentar margen inferior
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.4,  # Posición ajustada
                xanchor="center",
                x=0.5,
                font=dict(color="#333"),
                bgcolor='rgba(255,255,255,0.7)'
            ),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color="#333"),
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
                font_family="Open Sans"
            )
        )
        
        return fig
# --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------  --------------
# --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------  --------------
# --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------  --------------
# --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------  --------------
# --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------  --------------

    # Variables reactivas para equipos
    team_seasons = reactive.Value({})
    available_competitions = reactive.Value([])

    # Actualizar opciones de equipos y competiciones
    @reactive.Effect
    def _():
        teams = df3['team_name'].unique().tolist()
        competitions = df3['competition_name'].unique().tolist()
        ui.update_selectize("teams", choices=teams)
        ui.update_selectize("competitions", choices=competitions)
        

    # Categorías de métricas para equipos
    team_metric_categories = reactive.Value({
        'Métricas Básicas': [
            'BYPASSED_OPPONENTS',
            'BYPASSED_DEFENDERS',
            'GOALS',
            'ASSISTS',
            'SHOT_XG',
            'PACKING_XG',
            'SUCCESSFUL_PASSES',
            'UNSUCCESSFUL_PASSES',
            'OFFENSIVE_TOUCHES',
            'DEFENSIVE_TOUCHES'
        ],
        'Posesión y Progresión': [
            'BYPASSED_OPPONENTS_BY_ACTION_LOW_PASS',
            'BYPASSED_OPPONENTS_BY_ACTION_DIAGONAL_PASS',
            'BYPASSED_OPPONENTS_BY_ACTION_CHIPPED_PASS',
            'BYPASSED_OPPONENTS_BY_ACTION_SHORT_AERIAL_PASS',
            'BYPASSED_OPPONENTS_BY_ACTION_LOW_CROSS',
            'BYPASSED_OPPONENTS_BY_ACTION_HIGH_CROSS'
        ],
        'Transiciones': [
            'BALL_LOSS_ADDED_OPPONENTS',
            'BALL_LOSS_REMOVED_TEAMMATES',
            'BALL_WIN_ADDED_TEAMMATES',
            'BALL_WIN_REMOVED_OPPONENTS',
            'REVERSE_PLAY_ADDED_OPPONENTS'
        ],
        'Zonas del Campo': [
            'BYPASSED_OPPONENTS_FROM_PITCH_POSITION_OWN_BOX',
            'BYPASSED_OPPONENTS_FROM_PITCH_POSITION_FIRST_THIRD',
            'BYPASSED_OPPONENTS_FROM_PITCH_POSITION_MIDDLE_THIRD',
            'BYPASSED_OPPONENTS_FROM_PITCH_POSITION_FINAL_THIRD',
            'BYPASSED_OPPONENTS_FROM_PITCH_POSITION_OPPONENT_BOX'
        ],
        'Fases del Juego': [
            'BYPASSED_OPPONENTS_AT_PHASE_IN_POSSESSION',
            'BYPASSED_OPPONENTS_AT_PHASE_ATTACKING_TRANSITION',
            'BYPASSED_OPPONENTS_AT_PHASE_SET_PIECE',
            'BYPASSED_OPPONENTS_AT_PHASE_SECOND_BALL'
        ],
        'Defensa': [
            'SUFFERED_BYPASSED_OPPONENTS',
            'SUFFERED_BYPASSED_DEFENDERS',
            'OPPONENT_GOALS',
            'WON_GROUND_DUELS',
            'WON_AERIAL_DUELS'
        ],
        'Eficiencia': [
            'RATIO_GOALS_SHOT_XG',
            'RATIO_SHOTS_ON_TARGET',
            'RATIO_PASSING_ACCURACY'
        ]
    })

    @render.ui
    def dynamic_team_metric_selector():
        categories = team_metric_categories.get()
        metric_elements = []
        
        for category, metrics in categories.items():
            category_id = category.lower().replace(" ", "_")
            metric_elements.append(
                ui.div(
                    ui.div(
                        ui.div(
                            ui.span(category, class_="metric-category-title"),
                            ui.span(
                                ui.HTML('<i class="fas fa-chevron-down"></i>'),
                                id=f"team_icon_{category_id}"
                            ),
                            style="display: flex; justify-content: space-between; align-items: center;"
                        ),
                        onclick=f"toggleTeamCategory('{category_id}')",
                        class_="metric-category-header"
                    ),
                    ui.div(
                        ui.div(
                            ui.input_action_button(
                                f"team_select_all_{category_id}",
                                "Seleccionar todos",
                                class_="btn btn-sm btn-outline-primary mb-2 mr-2",
                                onclick=f"selectAllTeamMetrics('{category_id}', true)"
                            ),
                            ui.input_action_button(
                                f"team_deselect_all_{category_id}",
                                "Deseleccionar todos",
                                class_="btn btn-sm btn-outline-secondary mb-2",
                                onclick=f"selectAllTeamMetrics('{category_id}', false)"
                            ),
                            class_="mb-2"
                        ),
                        ui.div(
                            *[
                                ui.div(
                                    ui.input_checkbox(
                                        f"team_metric_{metric}",
                                        metric,
                                        value=False
                                    ),
                                    class_="metric-item"
                                )
                                for metric in metrics
                            ],
                            class_="metric-items",
                            id=f"team_metrics_{category_id}"
                        ),
                        class_="metric-category-content",
                        id=f"team_content_{category_id}"
                    ),
                    class_="metric-category",
                    id=f"team_category_{category_id}"
                )
            )
        
        return ui.TagList(
            ui.tags.script("""
                // Hacer las funciones globales
                window.toggleTeamCategory = function(categoryId) {
                    const content = document.getElementById(`team_content_${categoryId}`);
                    const icon = document.getElementById(`team_icon_${categoryId}`);
                    
                    if (content.style.display === 'none' || !content.style.display) {
                        content.style.display = 'block';
                        icon.innerHTML = '<i class="fas fa-chevron-up"></i>';
                    } else {
                        content.style.display = 'none';
                        icon.innerHTML = '<i class="fas fa-chevron-down"></i>';
                    }
                };
                
                window.selectAllTeamMetrics = function(categoryId, select) {
                    const checkboxes = document.querySelectorAll(`#team_metrics_${categoryId} input[type="checkbox"]`);
                    checkboxes.forEach(checkbox => {
                        checkbox.checked = select;
                        // Disparar el evento change para que Shiny se entere del cambio
                        const event = new Event('change', { bubbles: true });
                        checkbox.dispatchEvent(event);
                    });
                };
                
                // Inicializar todas las categorías como colapsadas
                document.querySelectorAll('.metric-category-content').forEach(el => {
                    el.style.display = 'none';
                });
            """),
            *metric_elements
        )

    # Selectores de temporada para cada equipo
    @render.ui
    def team_season_selectors():
        teams = input.teams()
        if not teams:
            return None
        
        season_selectors = []
        for team in teams:
            available_seasons = df3[df3['team_name'] == team]['season_name'].unique().tolist()
            safe_team_id = sanitize_id(team)
            season_id = f"team_season_{safe_team_id}"
            season_selectors.append(
                ui.div(
                    ui.input_select(
                        season_id,
                        f"Temporada para {team}",
                        choices=available_seasons,
                        selected=available_seasons[0] if available_seasons else None,
                        width="100%"
                    ),
                    class_="season-selector-card animated"
                )
            )
        
        return ui.div(
            ui.h4("Selección de Temporadas", class_="card-title"),
            ui.div(
                *season_selectors,
                class_="season-selectors-container"
            ),
            class_="mt-3"
        )

    # Actualizar temporadas seleccionadas
    @reactive.Effect
    def update_team_seasons():
        teams = input.teams()
        current = {}
        for team in teams:
            season_id = f"team_season_{sanitize_id(team)}"
            current[team] = input[season_id]()
        team_seasons.set(current)

    # Obtener métricas seleccionadas para equipos
    @reactive.Calc
    def selected_team_metrics():
        categories = team_metric_categories.get()
        return [metric for metrics in categories.values() 
                for metric in metrics if input[f"team_metric_{metric}"]()]

    # Tabla comparativa de equipos
    @render.ui
    def team_comparison_table():
        teams = input.teams()
        competitions = input.competitions()
        metrics = selected_team_metrics()
        group_type = input.team_comparison_group()
        
        if not teams or not metrics:
            return ui.div(
                    "Por favor selecciona al menos un equipo y algunas métricas para generar la tabla comparativa.",
                    class_="alert alert-info my-4",
                    role="alert"
                ),
        
        # Construir dataframe con los datos
        table_data = []
        for metric in metrics:
            row = {"Métrica": ui.span(metric, class_="highlight-cell")}
            
            # Valores de los equipos
            for team in teams:
                season = team_seasons.get().get(team)
                team_data = df3[(df3['team_name'] == team) & 
                            (df3['season_name'] == season)]
                
                if competitions:
                    team_data = team_data[team_data['competition_name'].isin(competitions)]
                
                if not team_data.empty and metric in team_data.columns:
                    # Calcular promedio si hay múltiples competiciones
                    value = team_data[metric].mean()
                    if value is not None:
                        row[team] = f"{value:.2f}" if isinstance(value, (int, float)) else str(value)
                    else:
                        row[team] = ui.span("N/D", style="color: #94a3b8;")
                else:
                    row[team] = ui.span("N/D", style="color: #94a3b8;")
            
            # Añadir grupo de comparación si corresponde
            if group_type == "liga" and competitions:
                league_data = df3[df3['competition_name'].isin(competitions)]
                
                if not league_data.empty and metric in league_data.columns:
                    avg = league_data[metric].mean()
                    row["Promedio Liga"] = ui.span(
                        f"{avg:.2f}",
                        class_="comparison-badge"
                    )
        
            table_data.append(row)

        # Convertir a DataFrame
        df_table = pd.DataFrame(table_data)
        
        # Renderizar tabla profesional con estilo
        return ui.HTML(
            df_table.to_html(
                classes="data-table",
                escape=False,
                index=False,
                border=0
            )
        )

    # Gráfico radar para equipos
    @render_widget
    def team_radar_chart_widget():
        teams = input.teams()
        competitions = input.competitions()
        metrics = selected_team_metrics()
        group_type = input.team_comparison_group()
        
        if not teams or not metrics:
            fig = go.Figure()
            fig.update_layout(
                title="Selecciona equipos y métricas para generar el gráfico",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color="#333")
            )
            return fig
        
        # Preparar datos de equipos
        traces = []
        colors = px.colors.qualitative.Plotly
        
        for i, team in enumerate(teams):
            season = team_seasons.get().get(team)
            team_data = df3[(df3['team_name'] == team) & 
                        (df3['season_name'] == season)]
            
            if competitions:
                team_data = team_data[team_data['competition_name'].isin(competitions)]
            
            if team_data.empty:
                continue
                
            # Calcular promedios si hay múltiples competiciones
            team_avg = team_data[metrics].mean()
            
            values = []
            for metric in metrics:
                if metric in team_avg:
                    # Normalizar basado en todos los equipos
                    metric_values = df3[metric].dropna()
                    
                    if len(metric_values) > 0:
                        low, high = np.percentile(metric_values, [5, 95])
                        val = team_avg[metric]
                        norm_value = (val - low) / (high - low) if (high - low) != 0 else 0.5
                        values.append(np.clip(norm_value, 0, 1))
                    else:
                        values.append(0.5)
                else:
                    values.append(0)
            
            traces.append(go.Scatterpolar(
                r=values + [values[0]],
                theta=metrics + [metrics[0]],
                fill='toself',
                name=f"{team} ({season})",
                line=dict(color=colors[i % len(colors)], width=2),
                opacity=0.8,
                hovertemplate="<b>%{theta}</b><br>Valor: %{r:.2f}<extra></extra>"
            ))
            
        # Añadir grupo de comparación si corresponde
        if group_type == "liga" and competitions:
            league_data = df3[df3['competition_name'].isin(competitions)]
            
            if not league_data.empty:
                league_avg = league_data[metrics].mean()
                group_values = []
                for metric in metrics:
                    if metric in league_avg:
                        # Usar mismos percentiles que para los equipos
                        metric_values = df3[metric].dropna()
                        
                        if len(metric_values) > 0:
                            low, high = np.percentile(metric_values, [5, 95])
                            avg = league_avg[metric]
                            norm_value = (avg - low) / (high - low) if (high - low) != 0 else 0.5
                            group_values.append(np.clip(norm_value, 0, 1))
                        else:
                            group_values.append(0.5)
                    else:
                        group_values.append(0)
                
                traces.append(go.Scatterpolar(
                    r=group_values + [group_values[0]],
                    theta=metrics + [metrics[0]],
                    fill='toself',
                    name="Promedio Liga",
                    line=dict(color='#7f8c8d', width=2, dash='dot'),
                    opacity=0.4,
                    hovertemplate="<b>%{theta}</b><br>Valor promedio: %{r:.2f}<extra></extra>"
                ))
        
        # Configuración final del gráfico
        fig = go.Figure(data=traces)
        fig.update_layout(
            polar=dict(
                radialaxis=dict(
                    visible=True,
                    range=[0, 1],
                    tickvals=[0, 0.5, 1],
                    ticktext=['Percentil 5', 'Mediana', 'Percentil 95'],
                    gridcolor='#e2e8f0',
                    linecolor='#e2e8f0',
                    tickfont=dict(color='#64748b')
                ),
                angularaxis=dict(
                    gridcolor='#e2e8f0',
                    linecolor='#e2e8f0',
                    tickfont=dict(color='#64748b')
                ),
                bgcolor='rgba(0,0,0,0)'
            ),
            height=500,
            width=800,
            margin=dict(l=80, r=80, t=80, b=200),
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=-0.4,
                xanchor="center",
                x=0.5,
                font=dict(color="#333"),
                bgcolor='rgba(255,255,255,0.7)'
            ),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color="#333"),
            hoverlabel=dict(
                bgcolor="white",
                font_size=12,
                font_family="Open Sans"
            )
        )
        
        return fig

    @render_widget
    def team_trend_chart():
        teams = input.teams()
        metric = input.trend_metric()
        
        if not teams or not metric:
            fig = go.Figure()
            fig.update_layout(
                title="Selecciona equipos y una métrica para ver su evolución",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)',
                font=dict(color="#333")
            )
            return fig
        
        fig = go.Figure()
        colors = px.colors.qualitative.Plotly
        
        # Obtener todas las temporadas únicas y ordenarlas
        all_seasons = sorted(df3['season_name'].unique(), 
                            key=lambda x: int(x.split('/')[0]))
        
        for i, team in enumerate(teams):
            team_data = df3[df3['team_name'] == team]
            
            if team_data.empty or metric not in team_data.columns:
                continue
                
            # Ordenar por temporada
            team_data = team_data.sort_values('season_name', 
                                            key=lambda x: x.str.split('/').str[0].astype(int))
            
            fig.add_trace(go.Scatter(
                x=team_data['season_name'],
                y=team_data[metric],
                name=team,
                mode='lines+markers',
                line=dict(color=colors[i % len(colors)], width=2),
                marker=dict(size=8),
                hovertemplate=f"<b>{team}</b><br>Temporada: %{{x}}<br>{metric}: %{{y:.2f}}<extra></extra>"
            ))
        
        fig.update_layout(
            title=f"Evolución de {metric} por temporada",
            xaxis_title="Temporada",
            yaxis_title=metric,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color="#333"),
            hovermode="closest",
            margin=dict(l=50, r=50, t=50, b=50),
            xaxis=dict(
                categoryorder='array',
                categoryarray=all_seasons
            )
        )
        
        return fig

    # Actualizar opciones de métricas para el gráfico de tendencia
    @reactive.Effect
    def update_trend_metric_choices():
        metrics = selected_team_metrics()
        ui.update_select("trend_metric", choices=metrics)
            
    import re

    def sanitize_id(name):
        # Reemplaza caracteres no alfanuméricos por guion bajo
        return re.sub(r'\W+', '_', name)

# --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------
# --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------
# --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------

    @reactive.Effect
    @reactive.event(input.team1_name)
    def _():
        if not input.team1_name():
            ui.update_selectize("team1_season", choices=[], selected=None)
            return
        
        seasons = data_objects['team_seasons'].get(input.team1_name(), [])
        ui.update_selectize("team1_season", 
                        choices=seasons, 
                        selected=seasons[0] if seasons else None)
    
    @reactive.Effect
    @reactive.event(input.team2_name)
    def _():
        if not input.team2_name():
            return
        seasons = data_objects['team_seasons'].get(input.team2_name(), []) 
        ui.update_selectize("team2_season", 
                        choices=seasons, 
                        selected=seasons[0] if seasons else None)
    
    @reactive.Calc
    def team1_data():
        if not input.team1_name() or not input.team1_season():
            return None
        try:
            return data_objects['df'][
                (data_objects['df']['team_name'] == input.team1_name()) & 
                (data_objects['df']['season_name'] == input.team1_season())
            ].iloc[0]
        except IndexError:
            return None
        
    @reactive.Calc
    def team2_data():
        if not input.team2_name() or not input.team2_season():
            return None
        try:
            return data_objects['df'][
                (data_objects['df']['team_name'] == input.team2_name()) & 
                (data_objects['df']['season_name'] == input.team2_season())
            ].iloc[0]
        except IndexError:
            return None
    
    @output
    @render.ui
    def team1_card():
        team_data = team1_data()
        if team_data is None:
            return ui.tags.div("Seleccione un equipo y temporada", class_="text-muted")
        
        return ui.tags.div(
            ui.tags.h4(team_data['team_name'], class_="card-title"),
            ui.tags.p(f"Temporada: {team_data['season_name']}", class_="card-text"),
            ui.tags.p(f"Competición: {team_data['competition_name']}", class_="card-text"),
            ui.tags.p(f"Partidos: {team_data['team_season_matches']}", class_="card-text"),
            ui.tags.p(f"Cluster: {team_data['cluster_name']}", class_="card-text"),
            ui.tags.hr(),
            ui.tags.h5("Métricas clave:", class_="mt-3"),
            *[ui.tags.p(f"{metric}: {float(team_data[metric]):.2f}" if isinstance(team_data[metric], (int, float)) else f"{metric}: {team_data[metric]}", 
                    class_="card-text small") 
            for metric in data_objects['selected_columns']]
        )
    
    @output
    @render.ui
    def team2_card():
        team_data = team2_data()
        if team_data is None:
            return ui.tags.div("Seleccione un equipo y temporada", class_="text-muted")
        
        return ui.tags.div(
            ui.tags.h4(team_data['team_name'], class_="card-title"),
            ui.tags.p(f"Temporada: {team_data['season_name']}", class_="card-text"),
            ui.tags.p(f"Competición: {team_data['competition_name']}", class_="card-text"),
            ui.tags.p(f"Partidos: {team_data['team_season_matches']}", class_="card-text"),
            ui.tags.p(f"Cluster: {team_data['cluster_name']}", class_="card-text"),
            ui.tags.hr(),
            ui.tags.h5("Métricas clave:", class_="mt-3"),
            *[ui.tags.p(f"{metric}: {team_data[metric]:.2f}"if isinstance(team_data[metric], (int, float)) else f"{metric}: {team_data[metric]}", 
                        class_="card-text small") 
              for metric in data_objects['selected_columns']]
        )

    
    def find_similar_teams(team_name, season_name):
        base_values = get_scaled_values(team_name, season_name)
        if base_values is None:
            return pd.DataFrame()

        # Filtrar los otros equipos
        other_teams = data_objects['df'][
            ~((data_objects['df']['team_name'] == team_name) & 
            (data_objects['df']['season_name'] == season_name))
        ]
        
        if len(other_teams) == 0:
            return pd.DataFrame()
        
        # Extraer y limpiar columnas seleccionadas
        other_df = other_teams[data_objects['selected_columns']].copy()
        other_df = other_df.replace(',', '.', regex=True).astype(float)

        # Escalar
        other_values = data_objects['scaler'].transform(other_df)

        # Calcular similitudes
        similarities = cosine_similarity(base_values, other_values)[0]

        # Preparar resultado
        similar_teams = other_teams.copy()
        similar_teams['similarity'] = similarities

        return similar_teams.sort_values('similarity', ascending=False).head(10)

    
    @output
    @render.ui
    def similar_teams_team1():
        team1 = team1_data()
        if team1 is None:
            return ui.tags.div("Seleccione un equipo y temporada", class_="text-muted")
        
        similar = find_similar_teams(team1['team_name'], team1['season_name'])
        return render_similar_teams_table(similar, "#dc3545")
    
    @output
    @render.ui
    def similar_teams_team2():
        team2 = team2_data()
        if team2 is None:
            return ui.tags.div("Seleccione un equipo y temporada", class_="text-muted")
        
        similar = find_similar_teams(team2['team_name'], team2['season_name'])
        return render_similar_teams_table(similar, "#0d6efd")
    
    def render_similar_teams_table(similar_teams, color):
        if similar_teams.empty:
            return ui.tags.div("No se encontraron equipos similares", class_="text-muted")
        
        cards = []
        for _, row in similar_teams.iterrows():
            similarity_percent = round(row['similarity'] * 100, 1)
            badge_class = "bg-success" if similarity_percent > 85 else \
                         "bg-primary" if similarity_percent > 70 else \
                         "bg-warning text-dark"
            
            cards.append(
                ui.tags.div(
                    ui.tags.div(
                        ui.tags.div(
                            ui.tags.h5(row['team_name'], class_="card-title mb-1"),
                            ui.tags.p(
                                f"{row['season_name']} | {row['competition_name']}",
                                class_="card-text small text-muted mb-1"
                            ),
                            ui.tags.p(
                                f"{row['cluster_name']} | Partidos: {row['team_season_matches']}",
                                class_="card-text small mb-2"
                            ),
                            ui.tags.div(
                                ui.tags.span(
                                    f"Similitud: {similarity_percent}%",
                                    class_=f"badge {badge_class} similarity-badge"
                                ),
                                class_="text-center"
                            ),
                            class_="card-body"
                        ),
                        class_="card similar-team-card",
                        style=f"border-left: 4px solid {color};"
                    ),
                    class_="mb-3"
                )
            )
        
        return ui.tags.div(*cards)
    
    @output
    @render.text
    def similarity_score():
        team1 = team1_data()
        team2 = team2_data()
        
        if team1 is None or team2 is None:
            return "Seleccione ambos equipos para calcular la similitud"
        
        # Obtener valores escalados
        team1_scaled = get_scaled_values(team1['team_name'], team1['season_name'])
        team2_scaled = get_scaled_values(team2['team_name'], team2['season_name'])
        
        if team1_scaled is None or team2_scaled is None:
            return "Error al calcular la similitud"
        
        # Calcular similitud coseno
        similarity = cosine_similarity(team1_scaled, team2_scaled)[0][0]
        similarity_percent = round(similarity * 100, 1)
        
        # Añadir información de clusters
        cluster_info = ""
        if team1['cluster'] == team2['cluster']:
            cluster_info = " (mismo cluster)"
        else:
            cluster_info = " (clusters diferentes)"
        
        interpretation = "Muy similares" if similarity_percent > 85 else \
                    "Similares" if similarity_percent > 70 else \
                    "Moderadamente similares" if similarity_percent > 50 else \
                    "Poco similares"
        
        return f"Similitud coseno: {similarity_percent}% ({interpretation}){cluster_info}"
    
    
    # 3. Mejorar los gráficos
    @output
    @render_plotly
    def radar_chart2():
        try:
            team1 = team1_data()
            team2 = team2_data()
            
            if team1 is None or team2 is None:
                return go.Figure(layout={
                    'title': 'Seleccione ambos equipos para comparar',
                    'height': 400
                })
            
            metrics = data_objects['selected_columns']
            df = data_objects['df'].copy()
            
            # Asegurar que las métricas son numéricas
            for metric in metrics:
                if df[metric].dtype == object:
                    df[metric] = pd.to_numeric(df[metric].astype(str).str.replace(',', '.'), errors='coerce')
            
            # Obtener valores mínimos y máximos para normalización
            min_vals = df[metrics].min()
            max_vals = df[metrics].max()
            range_vals = max_vals - min_vals
            range_vals[range_vals == 0] = 1  # Evitar división por cero
            
            # Normalizar datos
            def normalize(row):
                normalized = {}
                for metric in metrics:
                    value = float(row[metric])
                    if metric in ['UNSUCCESSFUL_PASSES', 'CRITICAL_BALL_LOSS_NUMBER', 'OPPONENT_GOALS']:
                        # Invertir para métricas donde menos es mejor
                        normalized[metric] = 1 - (value - min_vals[metric]) / range_vals[metric]
                    else:
                        normalized[metric] = (value - min_vals[metric]) / range_vals[metric]
                return normalized
            
            team1_norm = normalize(team1)
            team2_norm = normalize(team2)
            
            # Nombres de métricas más legibles
            metric_names = {
                'GOALS': 'Goles',
                'SUCCESSFUL_PASSES': 'Pases exitosos',
                'BALL_WIN_NUMBER': 'Recuperaciones',
                'BYPASSED_OPPONENTS': 'Rivales superados',
                'UNSUCCESSFUL_PASSES': 'Pases fallidos (↓)',
                'CRITICAL_BALL_LOSS_NUMBER': 'Pérdidas críticas (↓)',
                'OPPONENT_GOALS': 'Goles recibidos (↓)'
            }
            
            theta = [metric_names.get(m, m) for m in metrics]
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatterpolar(
                r=[team1_norm[m] for m in metrics],
                theta=theta,
                fill='toself',
                name=f"{team1['team_name']} ({team1['season_name']})",
                line_color='#dc3545',
                opacity=0.8
            ))
            
            fig.add_trace(go.Scatterpolar(
                r=[team2_norm[m] for m in metrics],
                theta=theta,
                fill='toself',
                name=f"{team2['team_name']} ({team2['season_name']})",
                line_color='#0d6efd',
                opacity=0.8
            ))
            
            fig.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 1])
                ),
                showlegend=True,
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.1,
                    xanchor="center",
                    x=0.5
                ),
                margin=dict(l=50, r=50, t=50, b=80),
                height=450
            )
            
            return fig
        except Exception as e:
            print(f"Error in radar_chart: {str(e)}")
            return go.Figure()

    @output
    @render_plotly
    def tsne_plot():
        try:
            df = data_objects['df'].copy()
            team1 = team1_data()
            team2 = team2_data()
            
            fig = px.scatter(
                df, 
                x='TSNE_1', 
                y='TSNE_2',
                color='cluster_name',
                hover_data=['team_name', 'season_name', 'competition_name'],
                height=600
            )
            
            if team1 is not None:
                fig.add_trace(go.Scatter(
                    x=[team1['TSNE_1']],
                    y=[team1['TSNE_2']],
                    mode='markers',
                    marker=dict(size=15, color='red', symbol='star', line=dict(width=2, color='black')),
                    name=f"{team1['team_name']} ({team1['season_name']})"
                ))
            
            if team2 is not None:
                fig.add_trace(go.Scatter(
                    x=[team2['TSNE_1']],
                    y=[team2['TSNE_2']],
                    mode='markers',
                    marker=dict(size=15, color='blue', symbol='star', line=dict(width=2, color='black')),
                    name=f"{team2['team_name']} ({team2['season_name']})"
                ))
            
            fig.update_layout(
                title="Posición en el Espacio de Clústeres",
                legend_title_text='Cluster'
            )
            
            return fig
        except Exception as e:
            print(f"Error in tsne_plot: {str(e)}")
            return go.Figure()

    @output
    @render_plotly
    def cluster_heatmap():
        try:
            centroids = data_objects['kmeans'].cluster_centers_
            selected_metrics = data_objects['selected_columns']
            
            centroids_df = pd.DataFrame(
                centroids,
                columns=selected_metrics,
                index=[f'Cluster {i}' for i in range(centroids.shape[0])]
            )
            
            # Normalizar para mejor visualización
            centroids_normalized = (centroids_df - centroids_df.min()) / (centroids_df.max() - centroids_df.min())
            
            fig = px.imshow(
                centroids_normalized.T,
                labels=dict(x="Cluster", y="Métrica", color="Valor Normalizado"),
                color_continuous_scale='RdBu',
                aspect="auto",
                height=500
            )
            
            fig.update_layout(
                title="Características de los Clústeres",
                xaxis_title="Cluster",
                yaxis_title="Métrica"
            )
            
            return fig
        except Exception as e:
            print(f"Error in cluster_heatmap: {str(e)}")
            return go.Figure()
    
    def get_scaled_values(team_name, season_name):
        if not team_name or not season_name:
            return None
        
        try:
            # Obtener fila correspondiente
            team_row = data_objects['df'][
                (data_objects['df']['team_name'] == team_name) & 
                (data_objects['df']['season_name'] == season_name)
            ]
            
            if len(team_row) == 0:
                return None
            
            # Preparar datos en el orden correcto
            values = team_row[data_objects['selected_columns']].values.astype(float)
            
            # Convertir a DataFrame para mantener nombres
            values_df = pd.DataFrame(values, columns=data_objects['selected_columns'])
            
            # Escalar
            scaled_values = data_objects['scaler'].transform(values_df)
            
            return scaled_values
            
        except Exception as e:
            print(f"Error in get_scaled_values: {str(e)}")
            return None

# --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------
#  --------------   --------------  --------------  --------------  --------------  --------------  --------------  --------------

    current_page = reactive.Value(1)
    rows_per_page = 10
    sort_column = reactive.Value("IMPECT_SCORE_PACKING")
    sort_direction = reactive.Value(False)
    is_resetting = reactive.Value(False)
    active_position_tab = reactive.Value(None) 
    # 1. Primero, define una variable reactiva para controlar la invalidación
    update_trigger = reactive.Value(0)

    # 2. Modifica la función filtered_players para que dependa del trigger
    @reactive.Calc
    def filtered_players():
        """Filtra jugadores basado en los criterios seleccionados"""
        # Hacer que dependa del trigger aunque no lo use directamente
        update_trigger()
    
        # Make sure you're using the correct DataFrame - replace 'datos()' with your actual data source
        df_filtered = df.copy()  # Or whichever DataFrame contains player data
        df_filtered = df_filtered[df_filtered["playDuration"] >= (4530 * 0.30)]  # Mínimo 30% de minutos
        
        # Solo aplicar similitud si hay equipo seleccionado y el switch está activado
        if input.selected_team() and input.use_similarity_switch():
            df_filtered = apply_team_similarity_adjustment(df_filtered)
    
        return df_filtered


    def get_ordered_positions(df):
        positions = df["positions"].dropna().unique().tolist()
        return sorted(positions, key=lambda x: (get_position_order(x), x))

    @reactive.Calc
    def calculate_percentiles():
        df_filtered = filtered_sorted_data()
        score_columns = [
            "IMPECT_SCORE_PACKING", 
            "IMPECT_SCORE_WITHOUT_GOALS_PACKING", 
            "OFFENSIVE_IMPECT_SCORE_PACKING", 
            "DEFENSIVE_IMPECT_SCORE_PACKING"
        ]
        
        percentiles = {}
        
        if df_filtered.empty or 'positions' not in df_filtered.columns:
            return percentiles
        
        # Agrupar por posición
        grouped = df_filtered.groupby('positions')
        
        for position, group in grouped:
            percentiles[position] = {}
            for col in score_columns:
                if col in group.columns and not group[col].empty:
                    try:
                        percentiles[position][col] = {
                            '25': group[col].quantile(0.25),
                            '50': group[col].quantile(0.50),
                            '75': group[col].quantile(0.75),
                            '90': group[col].quantile(0.90)
                        }
                    except:
                        percentiles[position][col] = {
                            '25': 0, '50': 0, '75': 0, '90': 0
                        }
        
        return percentiles

    def get_team_scaled_values(team_name):
        """Obtiene valores escalados para un equipo (promedio de todas sus temporadas) solo si está en df4"""
        try:
            if 'df' not in data_objects or 'scaler' not in data_objects or 'selected_columns' not in data_objects:
                return None
                
            df = data_objects['df']
            
            # Verificar si el equipo existe en df4
            if team_name not in df['team_name'].unique():
                return None
                
            team_data = df[df['team_name'] == team_name]
            
            if team_data.empty:
                return None
            
            # Promedio de todas las temporadas del equipo
            avg_values = team_data[data_objects['selected_columns']].mean().values.reshape(1, -1)
            
            # Convertir a DataFrame con nombres de columnas para evitar el warning
            avg_df = pd.DataFrame(avg_values, columns=data_objects['selected_columns'])
            scaled_values = data_objects['scaler'].transform(avg_df)
            
            return scaled_values
        except Exception as e:
            print(f"Error en get_team_scaled_values: {str(e)}")
            return None

    @reactive.Calc
    def reference_team():
        return input.selected_team()

    @output
    @render.ui
    def team_similarity_info():
        if not input.selected_team():
            return ui.HTML('<div class="alert alert-info">Selecciona un equipo de referencia para activar el análisis de similitud</div>')
        
        return ui.HTML(f"""
            <div class="alert alert-success">
                <strong>Equipo de referencia:</strong> {input.selected_team()}<br>
                <small>Los jugadores se ponderarán según la similitud de su equipo con este</small>
            </div>
        """)

    @reactive.Calc
    def reference_team_data():
        team = reference_team()
        if not team:
            return None
        
        # Obtener datos escalados del equipo de referencia
        return get_team_scaled_values(team)

    # Modificar la función de similitud para considerar el interruptor
    def get_team_similarity(team_name):
        """Calcula la similitud con el equipo de referencia actual"""
        if not use_similarity() or not reference_team() or team_name == reference_team():
            return 1.0  # Máxima similitud si no usamos similitud, no hay referencia o es el mismo equipo
        
        # Verificar si ambos equipos están en df4
        df = data_objects['df']
        if team_name not in df['team_name'].unique() or reference_team() not in df['team_name'].unique():
            return 0.7  # Valor ligeramente positivo si alguno de los equipos no está en df4
        
        team_scaled = get_team_scaled_values(team_name)
        ref_team_scaled = reference_team_data()
        
        if team_scaled is None or ref_team_scaled is None:
            return 0.7  # Valor ligeramente positivo si no se puede calcular
        
        similarity = cosine_similarity(team_scaled, ref_team_scaled)[0][0]
        return max(0.5, min(similarity, 1.0))  # Limitar entre 0.5 y 1.0

    def apply_team_similarity_adjustment(player_df):
        """Aplica un ajuste a las métricas de los jugadores basado en la similitud con el equipo de referencia actual"""
        if player_df.empty or not reference_team():
            return player_df
        
        adjusted_df = player_df.copy()
        
        # Obtener la similitud para cada equipo de cada jugador (solo para equipos en df4)
        adjusted_df['team_similarity'] = adjusted_df.apply(
            lambda row: get_team_similarity(
                row['team_name'] if 'team_name' in row else row['squadName']
            ),
            axis=1
        )
        
        # Métricas a ajustar
        metrics_to_adjust = [
            "IMPECT_SCORE_PACKING", 
            "IMPECT_SCORE_WITHOUT_GOALS_PACKING", 
            "OFFENSIVE_IMPECT_SCORE_PACKING", 
            "DEFENSIVE_IMPECT_SCORE_PACKING"
        ]
        
        # Aplicar ajuste de similitud
        for metric in metrics_to_adjust:
            if metric in adjusted_df.columns:
                adjusted_df[metric] = adjusted_df[metric] * adjusted_df['team_similarity']
        
        return adjusted_df

    # Modificar la función para obtener los mejores jugadores
    def get_top_players(pos_df, metric):
        """Obtiene los mejores jugadores por métrica, con ajuste por similitud de equipo si está activado"""
        if use_similarity() and reference_team():
            # Aplicar ajuste de similitud
            pos_df = apply_team_similarity_adjustment(pos_df)
            
            # Crear una puntuación combinada que priorice similitud
            pos_df['combined_score'] = pos_df[metric] * (0.7 + 0.3 * pos_df['team_similarity'])
            return pos_df.sort_values('combined_score', ascending=False).head(5)
        else:
            # Ordenar solo por la métrica si no usamos similitud
            return pos_df.sort_values(metric, ascending=False).head(5)

    
    
    use_similarity = reactive.Value(True)
    update_trigger = reactive.Value(0)
    active_position_tab = reactive.Value(None)
        # 1. Variable reactiva para controlar la pestaña activa
    active_position_tab = reactive.Value(None)

    # 2. Modificar el efecto que controla las pestañas
    @reactive.Effect
    @reactive.event(input.position_tabs)
    def _():
        # Solo actualiza la pestaña activa cuando cambia por interacción del usuario
        active_position_tab.set(input.position_tabs())

# 3. Modificar la función principal para usar el valor reactivo
    @output
    @render.ui
    def resumen_posiciones_html():
        df = filtered_players()
        if df.empty:
            return ui.HTML('<div class="alert alert-info">No hay datos disponibles con los filtros actuales</div>')
        
        metrics = {
            "IMPECT_SCORE_PACKING": ("Score General", "#3498db"),
            "IMPECT_SCORE_WITHOUT_GOALS_PACKING": ("Score sin Goles", "#2ecc71"),
            "OFFENSIVE_IMPECT_SCORE_PACKING": ("Score Ofensivo", "#e74c3c"),
            "DEFENSIVE_IMPECT_SCORE_PACKING": ("Score Defensivo", "#f39c12")
        }
        
        positions = get_ordered_positions(df)
        
        # Establecer la pestaña activa inicial si no está definida
        if active_position_tab() is None and positions:
            active_position_tab.set(positions[0])
        
        position_panels = []
        for position in positions:
            pos_df = df[df["positions"] == position]
            
            metric_cards = []
            for metric, (metric_name, color) in metrics.items():
                if metric not in pos_df.columns:
                    continue
                    
                top_players = pos_df.sort_values(metric, ascending=False).head(5)
                
                players_list = []
                for i, (_, row) in enumerate(top_players.iterrows(), 1):
                    team_name = row.get('squadName', row.get('team_name', ''))
                    has_similarity = (use_similarity() and 
                                    input.selected_team() and 
                                    team_name in data_objects['df']['team_name'].unique())
                    
                    similarity_badge = ""
                    if has_similarity and 'team_similarity' in row:
                        similarity_percent = row['team_similarity'] * 100
                        similarity_badge = ui.span(
                            {"class": "badge bg-light text-dark ms-2", "style": "font-size: 0.75rem;"},
                            f"{similarity_percent:.0f}% similitud"
                        )
                    
                    player_card = ui.div(
                        {"class": "card mb-2"},
                        ui.div(
                            {"class": "card-body py-2"},
                            ui.div(
                                {"class": "d-flex justify-content-between align-items-center"},
                                ui.div(
                                    {"class": "d-flex align-items-center"},
                                    ui.span(
                                        {"class": f"badge bg-{i} me-2"},
                                        f"{i}º"
                                    ),
                                    ui.div(
                                        ui.div(
                                            {"class": "fw-bold"},
                                            row['playerName']
                                        ),
                                        ui.div(
                                            {"class": "text-muted small"},
                                            team_name
                                        )
                                    )
                                ),
                                ui.div(
                                    {"class": "d-flex align-items-center"},
                                    ui.span(
                                        {"class": "badge rounded-pill", "style": f"background-color: {color}"},
                                        f"{row[metric]:.2f}"
                                    ),
                                    similarity_badge
                                )
                            )
                        )
                    )
                    players_list.append(player_card)
                
                metric_cards.append(
                    ui.div(
                        {"class": "col-md-6 mb-4"},
                        ui.div(
                            {"class": "card"},
                            ui.div(
                                {"class": "card-header", "style": f"background-color: {color}; color: white;"},
                                metric_name
                            ),
                            ui.div(
                                {"class": "card-body"},
                                *players_list
                            )
                        )
                    )
                )
            
            position_panels.append(
                ui.nav_panel(
                    position,
                    ui.div(
                        {"class": "row"},
                        *metric_cards
                    )
                )
            )
        
        return ui.navset_card_tab(
            *position_panels,
            id="position_tabs",
            selected=active_position_tab(),
            header=ui.div(
                ui.h4("Top 5 jugadores por Posición"),
                ui.p(
                    {"class": "text-muted"},
                    "Se muestran los top 5 jugadores por cada métrica (mínimo 500 minutos jugados)"
                ),
                ui.div(
                    {"class": "alert alert-info mt-2 mb-0 py-2", "style": "font-size: 0.85rem;"},
                    ui.tags.b("Nota: "),
                    "El porcentaje de similitud solo se muestra para equipos con datos de clustering disponibles"
                ) if use_similarity() and input.selected_team() else None
            )
        )

    # 4. Añadir un efecto para mantener la pestaña al cambiar equipos
    @reactive.Effect
    @reactive.event(input.selected_team)
    def _():
        # Cuando cambia el equipo, forzar que se mantenga la pestaña actual
        # Esto evita que se resetee la navegación
        if active_position_tab() is not None:
            active_position_tab.set(active_position_tab())

        # 3. Actualiza el efecto para modificar el trigger en lugar de invalidar
        @reactive.Effect
        @reactive.event(input.selected_team, input.use_similarity_switch)
        def update_display():
            # Incrementar el valor del trigger para forzar la actualización
            update_trigger.set(update_trigger() + 1)

        # Actualizar la pestaña activa cuando el usuario cambia de pestaña
        @reactive.Effect
        @reactive.event(input.tabs_positions)
        def _():
            active_position_tab.set(input.tabs_positions())
            
        # Añadir una variable reactiva para controlar si usamos similitud
        use_similarity = reactive.Value(True)

    # Modificar la UI para incluir un interruptor de similitud
    @output
    @render.ui
    def similarity_toggle():
        return ui.div(
            {"class": "form-check form-switch mb-3"},
            ui.input_switch(
                "use_similarity_switch", 
                "Usar ajuste por similitud de equipos", 
                value=use_similarity()
            ),
            ui.span(
                {"class": "form-check-label text-muted small"},
                "Cuando está activado, se ponderan los jugadores según la similitud de su equipo con el equipo de referencia"
            )
    )
        
        # Actualizar el valor reactivo cuando cambia el interruptor
    @reactive.Effect
    @reactive.event(input.use_similarity_switch)
    def _():
        use_similarity.set(input.use_similarity_switch())

app = App(app_ui, server)
