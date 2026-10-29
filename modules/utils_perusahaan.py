import re


def ambil_kecamatan_dari_alamat(alamat):

    alamat = str(
        alamat
        or ""
    ).strip()

    if not alamat:
        return ""

    match = re.search(
        r"\bKecamatan\s+"
        r"(.+?)"
        r"(?="
        r"\s+(?:Kabupaten|Kota|Provinsi|Desa|Kelurahan|RT|RW)\b"
        r"|[,;\n]"
        r"|$"
        r")",
        alamat,
        re.IGNORECASE,
    )

    if not match:
        return ""

    return str(
        match.group(1)
    ).strip().title()