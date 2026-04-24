<!DOCTYPE html>
<html lang="fr">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agent Update Manager</title>
    <style>
        :root {
            --bg-color: #1a1b1e;
            --card-bg: #25262b;
            --primary: #4dabf7;
            --text: #e9ecef;
            --border: #373a40;
            --success: #69db7c;
            --error: #ff8787;
        }

        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background-color: var(--bg-color);
            color: var(--text);
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
        }

        .container {
            background-color: var(--card-bg);
            padding: 2rem;
            border-radius: 12px;
            box-shadow: 0 8px 16px rgba(0, 0, 0, 0.2);
            width: 400px;
            text-align: center;
        }

        h2 {
            margin-top: 0;
        }

        input[type="password"] {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border-radius: 6px;
            border: 1px solid var(--border);
            background: #2c2e33;
            color: white;
            box-sizing: border-box;
        }

        .drop-zone {
            border: 2px dashed var(--border);
            border-radius: 8px;
            padding: 40px;
            margin: 20px 0;
            transition: all 0.3s ease;
            cursor: pointer;
        }

        .drop-zone.dragover {
            border-color: var(--primary);
            background: rgba(77, 171, 247, 0.1);
        }

        #status {
            margin-top: 15px;
            font-size: 0.9em;
            min-height: 20px;
        }

        .success {
            color: var(--success);
        }

        .error {
            color: var(--error);
        }

        .hidden {
            display: none;
        }

        button {
            background: var(--primary);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            width: 100%;
        }

        button:hover {
            opacity: 0.9;
        }
    </style>
</head>

<body>

    <div class="container">
        <h2>Update Manager</h2>

        <div id="login-section">
            <p>Veuillez vous identifier</p>
            <input type="password" id="password" placeholder="Mot de passe serveur">
            <button onclick="checkLogin()">Connexion</button>
        </div>

        <div id="upload-section" class="hidden">
            <div class="drop-zone" id="dropZone">
                <p>Glissez le fichier <strong>repository.zip</strong> ici<br>ou cliquez pour parcourir</p>
                <input type="file" id="fileInput" accept=".zip" hidden>
            </div>
            <div id="progress" class="hidden">Traitement en cours...</div>

            <div id="file-list-container" style="margin-top: 20px; text-align: left;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
                    <h3 style="margin: 0;">Fichiers du repository</h3>
                    <button onclick="fetchFiles()"
                        style="width: auto; padding: 5px 10px; font-size: 0.8em;">Actualiser</button>
                </div>
                <div id="file-list"
                    style="background: #2c2e33; padding: 10px; border-radius: 6px; font-family: monospace; font-size: 0.9em; max-height: 200px; overflow-y: auto;">
                    Chargement...
                </div>
            </div>
        </div>

        <div id="status"></div>
    </div>

    <script>
        const STORAGE_KEY = 'srv_update_token';
        const dropZone = document.getElementById('dropZone');
        const fileInput = document.getElementById('fileInput');

        // Auto-login if session exists
        if (sessionStorage.getItem(STORAGE_KEY)) {
            showUpload();
        }

        function checkLogin() {
            const pwd = document.getElementById('password').value;
            if (pwd) {
                sessionStorage.setItem(STORAGE_KEY, pwd);
                showUpload();
            }
        }

        function showUpload() {
            document.getElementById('login-section').classList.add('hidden');
            document.getElementById('upload-section').classList.remove('hidden');
            fetchFiles();
        }

        // Drag & Drop events
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('dragover');
        });
        dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('dragover');
            if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files[0]);
        });
        dropZone.addEventListener('click', () => fileInput.click());
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length) handleUpload(e.target.files[0]);
        });

        async function handleUpload(file) {
            if (file.name !== 'repository.zip') {
                setStatus('Erreur: Le fichier doit s\'appeler repository.zip', 'error');
                return;
            }

            const formData = new FormData();
            formData.append('file', file);
            formData.append('password', sessionStorage.getItem(STORAGE_KEY));
            formData.append('action', 'upload');

            document.getElementById('progress').classList.remove('hidden');
            setStatus('Envoi et extraction...', '');

            try {
                const res = await fetch('upload.php', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();

                if (data.success) {
                    setStatus('Succès : Mise à jour déployée !', 'success');
                    fetchFiles();
                } else {
                    setStatus('Erreur : ' + data.message, 'error');
                }
            } catch (e) {
                setStatus('Erreur réseau : ' + e.message, 'error');
            } finally {
                document.getElementById('progress').classList.add('hidden');
                fileInput.value = ''; // Reset
            }
        }

        async function fetchFiles() {
            const listContainer = document.getElementById('file-list');
            listContainer.innerHTML = 'Chargement...';

            const pwd = sessionStorage.getItem(STORAGE_KEY);
            try {
                // Using POST to send password securely in body, not url
                const formData = new FormData();
                formData.append('password', pwd);
                formData.append('action', 'list');

                const res = await fetch('upload.php', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();

                if (data.success && data.files) {
                    if (data.files.length === 0) {
                        listContainer.innerHTML = '<i>Aucun fichier trouvé.</i>';
                        return;
                    }

                    let html = '<ul style="list-style: none; padding: 0; margin: 0;">';
                    data.files.forEach(f => {
                        const size = (f.size / 1024).toFixed(1) + ' KB';
                        // URL encode path segments for download link
                        const dlLink = 'repository/' + f.path.split('/').map(encodeURIComponent).join('/');

                        html += `<li style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #373a40;">
                            <div style="flex-grow: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; margin-right: 10px;">
                                <a href="${dlLink}" target="_blank" style="color: #4dabf7; text-decoration: none;" title="Télécharger">${f.path}</a>
                            </div>
                            <div style="flex-shrink: 0; display: flex; align-items: center; gap: 10px;">
                                <span style="color: #888; font-size: 0.85em;">${size} | ${f.date}</span>
                                <button onclick="deleteFile('${f.path.replace(/'/g, "\\'")}')" style="background: #ff8787; padding: 2px 8px; font-size: 0.8em; width: auto;">Suppr.</button>
                            </div>
                        </li>`;
                    });
                    html += '</ul>';
                    listContainer.innerHTML = html;
                } else {
                    const msg = data.message || 'Réponse invalide';
                    listContainer.innerHTML = '<span style="color: #ff8787;">Erreur: ' + msg + '</span>';

                    // Si mot de passe incorrect, on déconnecte
                    if (msg.includes("Mot de passe incorrect")) {
                        sessionStorage.removeItem(STORAGE_KEY);
                        setTimeout(() => {
                            location.reload();
                        }, 2000);
                    }
                }
            } catch (e) {
                listContainer.innerHTML = '<span style="color: #ff8787;">Erreur réseau</span>';
            }
        }

        async function deleteFile(path) {
            if (!confirm("Voulez-vous vraiment supprimer " + path + " ?")) return;

            const pwd = sessionStorage.getItem(STORAGE_KEY);
            const formData = new FormData();
            formData.append('password', pwd);
            formData.append('action', 'delete');
            formData.append('path', path);

            try {
                const res = await fetch('upload.php', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                if (data.success) {
                    fetchFiles();
                } else {
                    alert("Erreur: " + data.message);
                    if (data.message.includes("Mot de passe incorrect")) {
                        sessionStorage.removeItem(STORAGE_KEY);
                        location.reload();
                    }
                }
            } catch (e) {
                alert("Erreur réseau");
            }
        }

        function setStatus(msg, type) {
            const el = document.getElementById('status');
            el.textContent = msg;
            el.className = type;
        }
    </script>

</body>

</html>