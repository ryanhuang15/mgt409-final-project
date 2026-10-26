# Model and audit services

model.py contains the official OpenAI SDK adapter, bounded requests/retries, and
measured usage aggregation. audit.py records sanitized request, tool, validation,
and controller events. Headers and credentials are not stored. Runtime results
are ignored by Git; selected synthetic runs may be exported as course evidence.
For `gpt-6-luna`, usage summaries estimate standard token cost from reported
uncached input, cached input, and output totals. This estimate is not an invoice;
exact billed cost and account-specific charges are not returned by the completion.
