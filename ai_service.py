import streamlit as st
from openai import OpenAI
from supabase import create_client
from sentence_transformers import SentenceTransformer

# Muat model embedding (hanya sekali)
@st.cache_resource
def load_embedding_model():
    return SentenceTransformer('aisingapore/SEA-LION-E5-Embedding-600M')

# Koneksi ke Supabase
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def tanya_deepseek_dengan_rag(pertanyaan):
    """
    Mengirim pertanyaan ke DeepSeek dengan konteks data dari Supabase (RAG).
    """
    supabase = init_supabase()
    model = load_embedding_model()
    
    # 1. Ubah pertanyaan pengguna menjadi vektor
    vektor_pertanyaan = model.encode(pertanyaan).tolist()
    
    # 2. Cari data yang paling relevan di Supabase
    # 'match_count=5' berarti ambil 5 data paling mirip
    hasil_pencarian = supabase.rpc(
        'match_documents',
        {
            'query_embedding': vektor_pertanyaan,
            'match_threshold': 0.5, # Ambang batas kemiripan (0-1)
            'match_count': 5
        }
    ).execute()
    
    # 3. Gabungkan data yang ditemukan menjadi satu teks konteks
    konteks = "\n\n".join([item['content'] for item in hasil_pencarian.data])
    
    # 4. Buat prompt baru untuk DeepSeek
    prompt_sistem = (
        "Anda adalah asisten cerdas untuk aplikasi SMART METRO. "
        "Jawablah pertanyaan pengguna berdasarkan KONTEKS DATA berikut. "
        "Jika jawabannya tidak ada dalam konteks, katakan dengan jujur bahwa Anda tidak mengetahuinya.\n\n"
        f"KONTEKS DATA:\n{konteks}"
    )
    
    # 5. Kirim ke DeepSeek
    client = OpenAI(
        api_key=st.secrets["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com"
    )
    
    response = client.chat.completions.create(
        model="deepseek-flash",
        messages=[
            {"role": "system", "content": prompt_sistem},
            {"role": "user", "content": pertanyaan}
        ]
    )
    
    return response.choices[0].message.content
