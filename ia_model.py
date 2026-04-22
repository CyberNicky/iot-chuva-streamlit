def prever(chuva, umidade, local, dia_semana):
    risco_base = 0

    # risco por chuva
    if chuva > 60:
        risco_base += 2
    elif chuva > 30:
        risco_base += 1

    # risco por local (vulnerabilidade)
    if local in ["Ibura"]:
        risco_base += 2
    elif local in ["Afogados", "Várzea"]:
        risco_base += 1

    # classificação final
    if risco_base <= 1:
        return "BAIXO"
    elif risco_base == 2:
        return "MÉDIO"
    else:
        return "ALTO"