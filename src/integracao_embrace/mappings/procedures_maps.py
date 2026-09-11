from typing import List, Dict, Optional

POLOTRIAL_UNIQUE_EVENT_PROCEDURES_MAP: List[Dict[str, Optional[str]]] = [
    #1
    {
        "procedure_name": r"M[oóOÓ]dulo\s+Identifica[cçCÇ][aãAÃ]o\s+da\s+Paciente",
        # "co_procedimento": "",
        "redcap_check_field": "idp3", #IDP3. ID Paciente
        "redcap_date_field": "idp4" #IDP4. Data
    },
    #2
    {
        "procedure_name": r"Consulta\s+M[eéEÉ]dica",
        # "co_procedimento": "",
        "redcap_check_field": "cm_atendimento_dt", #CM_ATENDIMENTO_DT. Data do atendimento
        "redcap_date_field": "cm_atendimento_dt" #CM_ATENDIMENTO_DT. Data do atendimento
    },
    #3.
    {
        "procedure_name": r"M[oóOÓ]dulo\s+Sa[uúUÚ]de",
        # "co_procedimento": "",
        "redcap_check_field": "s0",
        "redcap_date_field": "s0"
    },
    #4.
    {
        "procedure_name": r"M[oóOÓ]dulo\s+Menopausa",
        # "co_procedimento": "",
        "redcap_check_field": "pm0",
        "redcap_date_field": "pm0"
    },
    #5.
    {
        "procedure_name": r"Question[aáAÁ]rio\s+da\s+Sa[uúUÚ]de\s+da\s+Mulher\s+-\s+WHQ",
        # "co_procedimento": "",
        "redcap_check_field": "whq0",
        "redcap_date_field": "whq0"
    },
    #6.
    {
        "procedure_name": r"Question[aáAÁ]rio\s+Short\s+Form\s-\s+SF-36",
        # "co_procedimento": "",
        "redcap_check_field": "sf36_0", 
        "redcap_date_field": "sf36_0" 
    },
    #7.
    {
        "procedure_name": r"Question[aáAÁ]rio\s+PHQ9",
        # "co_procedimento": "",
        "redcap_check_field": "phq9_0", 
        "redcap_date_field": "phq9_0" 
    },
    #8.
    {
        "procedure_name": r"Question[aáAÁ]rio\s+WPAI",
        # "co_procedimento": "",
        "redcap_check_field": "wpai0", 
        "redcap_date_field": "wpai0"
    },
    #9.
    {
        "procedure_name": r"Question[aáAÁ]rio\s+GAD-7",
        # "co_procedimento": "",
        "redcap_check_field": "gad7_0", 
        "redcap_date_field": "gad7_0"
    },
    
]