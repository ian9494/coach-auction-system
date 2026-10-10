"""Export a fetched authority results list, never local reconstructed awards."""
import csv


def export_results(path, results):
    fields = ('playerName','coachId','amount')
    rows = []
    for result in results:
        if (not isinstance(result, dict) or set(result) != set(fields) or
                not isinstance(result['playerName'], str) or not isinstance(result['coachId'], str) or
                type(result['amount']) is not int or result['amount'] < 0):
            raise ValueError('INVALID_RESULTS')
        # Neutralize spreadsheet formula injection in names, preserving numeric amount.
        rows.append({key: ("'" + result[key] if isinstance(result[key],str) and
                     result[key].lstrip().startswith(('=','+','-','@')) else result[key]) for key in fields})
    with open(path, 'w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
