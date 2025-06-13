"""
Module de surveillance du trafic réseau
---------------------------------------
Ce module fournit des informations sur la vitesse du trafic réseau en temps réel :
- Débit en octets envoyés par seconde
- Débit en octets reçus par seconde

Utilise la bibliothèque psutil pour lire les compteurs réseau du système.
Le débit est calculé en mesurant la différence entre deux points dans le temps.
"""

import psutil
import time

# Variables globales pour stocker les compteurs réseau et l'horodatage du dernier appel
last_time = None
last_counters = None

def get_data():
    """
    Récupère les vitesses réseau (débit en octets par seconde).
    
    Returns:
        dict: Dictionnaire contenant :
            - bytes_sent: Nombre d'octets envoyés par seconde (arrondi en entier)
            - bytes_recv: Nombre d'octets reçus par seconde (arrondi en entier)
    """
    global last_time, last_counters

    current_time = time.time()
    current_counters = psutil.net_io_counters()

    # Si c'est la première exécution, on initialise les valeurs sans calculer le débit
    if last_time is None or last_counters is None:
        last_time = current_time
        last_counters = current_counters
        return {
            "bytes_sent": 0,
            "bytes_recv": 0
        }

    # Calcul de l'intervalle de temps depuis la dernière mesure
    elapsed = current_time - last_time

    # Calcul du débit en octets par seconde
    sent_per_sec = (current_counters.bytes_sent - last_counters.bytes_sent) / elapsed
    recv_per_sec = (current_counters.bytes_recv - last_counters.bytes_recv) / elapsed

    # Mise à jour des compteurs pour la prochaine mesure
    last_time = current_time
    last_counters = current_counters

    return {
        "bytes_sent": int(sent_per_sec),
        "bytes_recv": int(recv_per_sec)
    }
