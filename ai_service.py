import streamlit as st
from openai import OpenAI


def tanya_deepseek(pertanyaan):
    """
    Mengirim pertanyaan ke DeepSeek dan mengembalikan jawabannya.
    """
    # 1. Ambil kartu akses dari brankas (Streamlit Secrets)
    client = OpenAI(
        api_key=st.secrets["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com"
    )
    
    # 2. Kirim pertanyaan ke DeepSeek
    response = client.chat.completions.create(
        model="deepseek-flash",
        messages=[
            {"role": "system", "content": "Anda adalah asisten cerdas untuk aplikasi SMART METRO."},
            {"role": "user", "content": pertanyaan}
        ]
    )
    
    # 3. Ambil teks jawabannya
    return response.choices[0].message.content