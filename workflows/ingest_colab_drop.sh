#!/usr/bin/env bash
# Processa zips soltos em results/colab-drive/: extrai, move cada pasta
# <accession>/ para results/<accession>/, e so entao apaga o zip original
# -- e so se TODAS as pastas foram confirmadas no destino. Se qualquer
# etapa falhar, para sem apagar nada (o zip fica ali para tentar de novo).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DROP_DIR="$ROOT/results/colab-drive"
DEST_DIR="$ROOT/results"

shopt -s nullglob
zips=("$DROP_DIR"/*.zip)
shopt -u nullglob

if [ ${#zips[@]} -eq 0 ]; then
    echo "Nenhum zip em $DROP_DIR. Nada a fazer."
    exit 0
fi

for zip in "${zips[@]}"; do
    echo "=== processando $(basename "$zip") ==="
    extract_dir="$DROP_DIR/_extracting_$(basename "$zip" .zip)"
    rm -rf "$extract_dir"
    mkdir -p "$extract_dir"

    unzip -q -o "$zip" -d "$extract_dir"

    # aceita tanto <acc>/... quanto results/<acc>/... dentro do zip
    src_root="$extract_dir"
    if [ -d "$extract_dir/results" ]; then
        src_root="$extract_dir/results"
    fi

    accessions=()
    for d in "$src_root"/*/; do
        [ -d "$d" ] || continue
        accessions+=("$(basename "$d")")
    done

    if [ ${#accessions[@]} -eq 0 ]; then
        echo "  ERRO: nenhuma pasta de accession encontrada dentro do zip. Abortando, zip mantido."
        rm -rf "$extract_dir"
        continue
    fi

    moved=()
    skipped=()
    failed=()
    for acc in "${accessions[@]}"; do
        src="$src_root/$acc"
        dest="$DEST_DIR/$acc"
        # A re-uploaded results/ zip from Colab commonly repeats accessions
        # already ingested here -- that's expected, not an error. Discard
        # the duplicate copy from the zip and keep going; only a genuine
        # move failure should block deleting the zip below.
        if [ -e "$dest" ]; then
            echo "  ja existe em $dest -- descartando copia duplicada do zip."
            rm -rf "$src"
            skipped+=("$acc")
            continue
        fi
        mv "$src" "$dest" || true
        # Check the actual filesystem end-state rather than trusting mv's
        # exit code alone -- a prior run showed mv can print "Permission
        # denied" for some file inside the tree yet still leave the caller
        # thinking it succeeded, so verify dest is really there AND src is
        # really gone before counting it as moved.
        if [ -d "$dest" ] && [ ! -e "$src" ]; then
            echo "  movido: $acc"
            moved+=("$acc")
        else
            echo "  ERRO ao mover $acc (estado inesperado em origem/destino)"
            failed+=("$acc")
        fi
    done

    rm -rf "$extract_dir"

    if [ ${#failed[@]} -eq 0 ]; then
        rm -f "$zip"
        echo "  OK: ${#moved[@]} pastas movidas, ${#skipped[@]} ja existiam (descartadas do zip), zip removido."
    else
        echo "  ATENCAO: ${#failed[@]} pasta(s) com problema (${failed[*]}) -- zip MANTIDO em $zip para nao perder nada."
        echo "  ${#moved[@]} pasta(s) movida(s), ${#skipped[@]} ja existiam: ${moved[*]:-nenhuma}"
    fi
done
