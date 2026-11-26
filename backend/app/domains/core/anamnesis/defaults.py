from __future__ import annotations

from typing import Any

DEFAULT_PIERCING_TEMPLATE_TITLE = "Ficha de Anamnese e Termo de Consentimento — Body Piercing"

DEFAULT_PIERCING_FIELDS_SCHEMA: list[dict[str, Any]] = [
    {
        "key": "allergies",
        "label": "Possui alergia a metais (níquel/bijuteria), látex, iodo, clorexidina ou medicamentos?",
        "type": "boolean_with_details",
        "required": True,
        "details_placeholder": "Descreva quais alergias possui",
    },
    {
        "key": "diabetes",
        "label": "Possui diabetes (Tipo 1, Tipo 2 ou gestacional)?",
        "type": "boolean",
        "required": True,
    },
    {
        "key": "blood_pressure",
        "label": "Possui hipertensão, hipotensão ou histórico de tontura/desmaio com agulhas?",
        "type": "boolean",
        "required": True,
    },
    {
        "key": "coagulation_disorders",
        "label": "Possui distúrbio de coagulação sanguínea ou sangramento excessivo?",
        "type": "boolean",
        "required": True,
    },
    {
        "key": "keloid_history",
        "label": "Possui histórico de queloides ou cicatrização hipertrófica?",
        "type": "boolean",
        "required": True,
    },
    {
        "key": "medications",
        "label": "Faz uso de medicamentos contínuos (ex.: anticoagulantes, corticoides, Roacutan/isotretinoína)?",
        "type": "text",
        "required": False,
        "placeholder": "Informe os medicamentos em uso ou deixe em branco",
    },
    {
        "key": "pregnant_or_nursing",
        "label": "Está gestante ou amamentando?",
        "type": "boolean",
        "required": True,
    },
    {
        "key": "infectious_diseases",
        "label": "Possui alguma doença infectocontagiosa ou inflamação ativa no local da perfuração?",
        "type": "boolean",
        "required": True,
    },
    {
        "key": "fed_recently",
        "label": "Alimentou-se adequadamente nas últimas 4 horas e não ingeriu bebidas alcoólicas/drogas hoje?",
        "type": "boolean",
        "required": True,
    },
    {
        "key": "additional_notes",
        "label": "Observações adicionais relevantes sobre sua saúde",
        "type": "textarea",
        "required": False,
        "placeholder": "Alguma cirurgia recente, condição cardíaca, epilepsia ou observação?",
    },
]

DEFAULT_PIERCING_CONSENT_TEXT = (
    "DECLARAÇÃO DE SAÚDE, BIOSSEGURANÇA E CONSENTIMENTO LIVRE E ESCLARECIDO (LGPD):\n\n"
    "1. Declaro que todas as informações de saúde fornecidas nesta ficha são verdadeiras e completas, "
    "isentando o estúdio e o(a) profissional por complicações decorrentes de informações omitidas.\n"
    "2. Estou ciente de que a perfuração corporal é um procedimento invasivo sujeito a reações naturais "
    "do organismo (inchaço inicial, vermelhidão leve e sensibilidade) e que o sucesso da cicatrização "
    "depende diretamente do cumprimento rigoroso das orientações de cuidados pós-procedimento.\n"
    "3. Comprometo-me a retornar ao estúdio no prazo indicado para avaliação e realização do downsize "
    "(troca por haste menor após redução do inchaço), evitando traumas, angulação ou granulomas.\n"
    "4. Autorizo o tratamento confidencial dos dados sensíveis desta ficha exclusivamente para fins de "
    "segurança clínica, rastreabilidade sanitária e cumprimento de obrigações legais, nos termos da "
    "Lei Geral de Proteção de Dados (Lei nº 13.709/2018 — Art. 11)."
)
