<?php
header('Content-Type: application/json');

// --- CONFIGURATION ---

$LOGIN_PASSWORD = 'P%jFAu$hGFqB3t';
$TARGET_DIR = __DIR__ . '/repository';
// ---------------------

function json_out($success, $message)
{
    echo json_encode(['success' => $success, 'message' => $message]);
    exit;
}

// 1. Check Auth (POST or GET)
$pass = $_REQUEST['password'] ?? '';
if ($pass !== $LOGIN_PASSWORD) {
    // DEBUG: Affiche ce qu'on a reçu pour comprendre
    json_out(false, "Mot de passe incorrect.");
}

$action = $_REQUEST['action'] ?? 'upload';

if ($action === 'list') {
    $files = [];
    if (is_dir($TARGET_DIR)) {
        $iterator = new RecursiveIteratorIterator(
            new RecursiveDirectoryIterator($TARGET_DIR, RecursiveDirectoryIterator::SKIP_DOTS),
            RecursiveIteratorIterator::SELF_FIRST
        );

        foreach ($iterator as $file) {
            $path = $file->getRealPath();
            $relativePath = substr($path, strlen(realpath($TARGET_DIR)) + 1);
            // Fix slashes for consistency
            $relativePath = str_replace('\\', '/', $relativePath);

            if ($file->isFile()) {
                $files[] = [
                    'type' => 'file',
                    'path' => $relativePath,
                    'size' => $file->getSize(),
                    'date' => date('Y-m-d H:i:s', $file->getMTime())
                ];
            }
        }
    }
    // Sort by path
    usort($files, function ($a, $b) {
        return strcmp($a['path'], $b['path']);
    });

    echo json_encode(['success' => true, 'files' => $files]);
    exit;
}

if ($action === 'delete') {
    $path = $_POST['path'] ?? '';
    if (!$path)
        json_out(false, "Chemin manquant.");

    // Security check: Prevent ../ traversal
    $fullPath = realpath($TARGET_DIR . '/' . $path);
    if ($fullPath === false || strpos($fullPath, realpath($TARGET_DIR)) !== 0) {
        json_out(false, "Accès interdit (Chemin invalide).");
    }

    if (file_exists($fullPath)) {
        if (unlink($fullPath)) {
            json_out(true, "Fichier supprimé.");
        } else {
            json_out(false, "Erreur lors de la suppression.");
        }
    } else {
        json_out(false, "Fichier introuvable.");
    }
}

// 2. Check File (Only for upload action)
if (!isset($_FILES['file']) || $_FILES['file']['error'] !== UPLOAD_ERR_OK) {
    json_out(false, "Erreur d'upload (Code: " . ($_FILES['file']['error'] ?? 'N/A') . ")");
}

$zipPath = $_FILES['file']['tmp_name'];
$zipType = mime_content_type($zipPath);

// Basic magic number check for ZIP (PK..)
$handle = fopen($zipPath, 'rb');
$header = fread($handle, 4);
fclose($handle);
if ($header !== "PK\x03\x04") {
    json_out(false, "Le fichier n'est pas une archive ZIP valide.");
}

// 3. Process Update
try {
    $zip = new ZipArchive;
    if ($zip->open($zipPath) === TRUE) {

        // Backup Logic could go here (e.g. rename 'repository' to 'repository_bak')


        // ensure target dir exists
        if (!is_dir($TARGET_DIR)) {
            mkdir($TARGET_DIR, 0755, true);
        }

        // Extract
        // We assume the zip contains the 'repository' folder at root, OR contents.
        // If the user zipped the folder 'repository', we extract to __DIR__
        // If the user zipped the CONTENTS, we extract to $TARGET_DIR

        // Let's check first file index
        $firstInit = $zip->getNameIndex(0);

        // Safe bet: Extract to a temp dir first, then move, or just extract to __DIR__ 
        // assuming standard "zip -r repository.zip repository" usage.

        $zip->extractTo(__DIR__);
        $zip->close();

        // Validation: Check if repository exists now
        if (!is_dir($TARGET_DIR)) {
            json_out(false, "L'archive ne contenait pas de dossier 'repository' à la racine.");
        }

        // Permissions fix (optional, depending on umask)
        // chmod($TARGET_DIR, 0755);

        json_out(true, "Mise à jour réussie.");
    } else {
        json_out(false, "Impossible d'ouvrir le fichier ZIP.");
    }
} catch (Exception $e) {
    json_out(false, "Erreur serveur: " . $e->getMessage());
}
?>