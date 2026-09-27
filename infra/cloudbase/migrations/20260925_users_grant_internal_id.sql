BEGIN;

GRANT SELECT (id, auth_subject, status, deleted_at)
ON TABLE public.users
TO authenticated;

COMMIT;
