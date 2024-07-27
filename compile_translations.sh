#!/bin/bash

locales_dir="locales"
languages=("en" "ru" "am")

for lang in "${languages[@]}"; do
    po_file="${locales_dir}/${lang}/LC_MESSAGES/messages.po"
    mo_file="${locales_dir}/${lang}/LC_MESSAGES/messages.mo"
    if [ -f "$po_file" ]; then
        msgfmt "$po_file" -o "$mo_file"
        echo "Generated $mo_file"
    else
        echo "File $po_file does not exist"
    fi
done
