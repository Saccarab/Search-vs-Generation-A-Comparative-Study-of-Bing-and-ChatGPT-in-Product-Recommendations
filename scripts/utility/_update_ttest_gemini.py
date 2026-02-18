
import os

def update_data_viewer_gemini():
    file_path = 'scripts/utility/data_viewer.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Replace the placeholder Gemini vs GPT Personal table with the actual Gemini Order vs Menu table
    content = content.replace('<h2 style="font-size: 14px; margin-top:0;">Gemini vs. GPT Personal</h2>', '<h2 style="font-size: 14px; margin-top:0;">Gemini Selection Preference (Order vs. Menu)</h2>')
    content = content.replace('<th style="text-align:right;">Gem %</th>', '<th style="text-align:right;">Order %</th>')
    content = content.replace('<th style="text-align:right;">GPT %</th>', '<th style="text-align:right;">Menu %</th>')
    content = content.replace('ttests.gemini_vs_gpt_all.items()', 'ttests.gemini_order_vs_menu.items()')
    content = content.replace('{{ res.m1 }}%', '{{ res.m1 }}%') # No change needed but for completeness
    content = content.replace('{{ res.m2 }}%', '{{ res.m2 }}%')

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == "__main__":
    update_data_viewer_gemini()
    print('Successfully updated data_viewer.py with Gemini Order vs Menu T-tests.')
