"""
Module de surveillance réseau
-----------------------------
Calcule la bande passante utilisée (Upload/Download) en temps réel.

Exposed Functions:
- get_data(): Retourne les octets/seconde envoyés et reçus.
"""

import psutil
import time

# Variables globales pour stocker les compteurs réseau et l'horodatage du dernier appel
last_time = None
last_counters = None

def get_data():
    """
    Récupère le débit réseau actuel.

    Returns:
        dict:
            - bytes_sent (int): Upload en o/s
            - bytes_recv (int): Download en o/s
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

# Test
if __name__ == "__main__":
    print(get_data())