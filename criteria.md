# Capstone acceptance criteria

Shape B: hardening against store failures. Written before any results.

1. When one store is forced to time out (FITFINDR_FAIL_STORE=etsy:timeout), at least 9 of 10 searches still return results from the other stores.
   Why 9: if a user sees a blank page more than once in ten searches, they will decide the site is unreliable and not come back.

2. When a store fails, the results page names that store and the reason in plain words in at least 9 of 10 searches.
   Why 9: if users can't see why results are missing, they will think the whole site is broken and leave.

3. With one store timing out, a search finishes in under 3 seconds (warm server, not counting Render's first wake-up) in at least 9 of 10 searches.
   Why 3 seconds: secondhand shoppers usually wait about 3 seconds before closing a page; one slow search in ten is the most I accept.

4. Every failed store call writes one log record with timestamp, store, error type, latency and retry count, in 10 of 10 forced failures.
   Why 10: every user action and its result must be traceable at any time; one missing record means a failure I can never diagnose, which also hurts product iteration.

5. One search costs less than $0.01 on average over 10 searches (Gemini tokens, measured).
   Why $0.01: 100 users x 5 searches x 30 days = 15,000 searches a month; with a $150 monthly budget, each search must cost under $0.01, because users never pay per search across stores.