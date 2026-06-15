import asyncio
from typing import Any

from cap_client import fetch_budget_from_cap, fetch_vendors_from_cap


async def run_tests() -> bool:
    success = True
    print('\n=== CAP CLIENT TESTS ===')

    print('\n1) fetch_vendors_from_cap()')
    try:
        vendors = await fetch_vendors_from_cap('')
        print(f'   OK: returned {len(vendors)} vendors')
    except Exception as exc:
        print(f'   FAIL: {exc}')
        success = False

    print('\n2) fetch_vendors_from_cap("Electronics")')
    try:
        vendors = await fetch_vendors_from_cap('Electronics')
        print(f'   OK: returned {len(vendors)} vendors')
    except Exception as exc:
        print(f'   FAIL: {exc}')
        success = False

    print('\n3) fetch_budget_from_cap("IT Department")')
    try:
        budget = await fetch_budget_from_cap('IT Department')
        print('   OK: budget returned')
        for key in ('department', 'totalBudget', 'spentAmount', 'reservedAmount'):
            print(f'      {key}: {budget.get(key)}')
    except Exception as exc:
        print(f'   FAIL: {exc}')
        success = False

    print('\n4) fetch_budget_from_cap("Nonexistent Department")')
    try:
        await fetch_budget_from_cap('Nonexistent Department')
        print('   FAIL: expected error, but got success')
        success = False
    except Exception as exc:
        print(f'   OK: expected failure: {exc}')

    return success


if __name__ == '__main__':
    result = asyncio.run(run_tests())
    if result:
        print('\nALL TESTS PASSED')
    else:
        print('\nSOME TESTS FAILED')
        raise SystemExit(1)
