BEGIN;

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.users FROM anon;
REVOKE ALL ON TABLE public.users FROM authenticated;

GRANT SELECT (auth_subject, status, deleted_at)
ON TABLE public.users
TO authenticated;

DROP POLICY IF EXISTS users_select_self ON public.users;

CREATE POLICY users_select_self
ON public.users
FOR SELECT
TO authenticated
USING (
    auth_subject = (SELECT auth.uid())::text
    AND deleted_at IS NULL
);

COMMIT;
