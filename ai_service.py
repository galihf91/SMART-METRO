import streamlit as st
from openai import OpenAI
from supabase import create_client
from sentence_transformers import SentenceTransformer


# =========================================================
# LOAD MODEL & KONEKSI (di-cache agar cepat)
# =========================================================
@st.cache_resource
def load_model():
    return SentenceTransformer('intfloat/multilingual-e5-small')


@st.cache_resource
def init_supabase():
    return create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )


# =========================================================
# FUNGSI UTAMA: TANYA DEEPSEEK DENGAN RAG
# =========================================================
def tanya_deepseek(pertanyaan):
    """
    Mengirim pertanyaan ke DeepSeek dengan konteks data dari Supabase (RAG).
    """
    supabase = init_supabase()
    model = load_model()

    # 1. Ubah pertanyaan jadi vektor (pakai prefix 'query: ')
    vektor_pertanyaan = model.encode(f"query: {pertanyaan}").tolist()

    # 2. Cari data paling relevan di Supabase
    hasil = supabase.rpc(
        'match_documents',
        {
            'query_embedding': vektor_pertanyaan,
            'match_threshold': 0.3,
            'match_count': 5
        }
    ).execute()

    # 3. Gabungkan hasil pencarian jadi konteks
    konteks = "\n\n".join([item['content'] for item in hasil.data])

    # 4. Buat prompt dengan konteks
    prompt_sistem = (
        "Anda adalah asisten cerdas untuk aplikasi SMART METRO "
        "milik Dinas Perindustrian dan Perdagangan Kabupaten Tangerang. "
        "Jawablah pertanyaan pengguna dengan sopan, singkat, dan akurat. "
        "Gunakan KONTEKS DATA berikut sebagai sumber utama jawaban. "
        "Jika jawaban tidak ada di konteks, katakan dengan jujur "
        "bahwa data tersebut belum tersedia.\n\n"
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
