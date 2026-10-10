-- ==============================================================================
-- AI Voice Studio — Phase 5B Gate A: Transactional QA Account Deactivation
-- Strictly sets is_active = 0 for the 13 QA test accounts.
-- Preserves ALL user rows, foreign key references, projects, jobs, and audio files.
-- DO NOT EXECUTE ON PRODUCTION UNTIL PRODUCT OWNER GATE A APPROVAL.
-- ==============================================================================

-- 1. Enable foreign key constraint enforcement before opening transaction
-- (In SQLite, PRAGMA foreign_keys is a no-op inside an open transaction)
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- 2. Deactivate the 7 automated test accounts with known passwords
--    and the 6 mock-seeded test accounts
UPDATE users
SET is_active = 0
WHERE username IN (
    'victim_account',
    'alice_shared',
    'bob_shared',
    'concurrent_user',
    'reset_user',
    'spoof_user',
    'real_existing_user',
    'healthy_user',
    'crashed_worker_user',
    'stale_user',
    'compete_user',
    'large_output_user',
    'export_fail_user'
);

-- 3. Verify exactly 13 rows were deactivated and acceptance_qa remains active
SELECT username, role, is_active
FROM users
ORDER BY username ASC;

-- 4. Check foreign key constraints
PRAGMA foreign_key_check;

COMMIT;
