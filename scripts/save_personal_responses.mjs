import fs from 'fs';
import path from 'path';
import { parse } from 'csv-parse/sync';

const outputDir = 'datapass/raw_network_responses';
const personalCSV = 'datapass/personal_data_run/chatgpt_results_2026-01-28T02-25-34.csv';

const data = fs.readFileSync(personalCSV, 'utf-8');
const rows = parse(data, { columns: true });

let saved = 0;
rows.forEach(row => {
    const filename = path.join(outputDir, `${row.prompt_id}_r${row.run_number}_personal.json`);
    
    const responseData = {
        query_index: row.query_index,
        run_number: row.run_number,
        prompt_id: row.prompt_id,
        query: row.query,
        generated_search_query: row.generated_search_query,
        hidden_queries_json: row.hidden_queries_json,
        search_result_groups_json: row.search_result_groups_json,
        content_references_json: row.content_references_json,
        sonic_classification_json: row.sonic_classification_json,
        response_text: row.response_text,
        web_search_forced: row.web_search_forced,
        web_search_triggered: row.web_search_triggered,
        items_json: row.items_json,
        items_count: row.items_count,
        items_with_citations_count: row.items_with_citations_count,
        sources_cited_json: row.sources_cited_json,
        sources_additional_json: row.sources_additional_json,
        sources_all_json: row.sources_all_json,
        account_type: 'personal'
    };
    
    fs.writeFileSync(filename, JSON.stringify(responseData, null, 2));
    saved++;
});

console.log(`✅ Saved ${saved} personal network response files to ${outputDir}`);
