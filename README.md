# Physique OS

A single-file personal fitness dashboard: body weight, calories/macros,
today's training session, water, meals, supplements, and sleep — all in one
HTML page. It's built for one user, not a multi-account product.

Data (daily ticks, weight history, lift logs) is stored in Supabase under
one account, so it persists across devices and survives a refresh. If
Supabase is unreachable, the page keeps working locally in memory; it just
won't save until connectivity comes back.

## Running it locally

There's no build step and no server required.

1. Open `physique-os.html` directly in a browser (double-click it, or
   right-click → Open with → your browser).
2. Log in with your Supabase account email and password.

That's it — everything else (the dashboard, the Supabase client, the auth
gate) is self-contained in that one file.

## Deploying to Render (free static site)

1. Push this repo to GitHub (already done if you're reading this from
   `github.com/IshuSahu/Fitness-Tracker`).
2. On [Render](https://render.com), click **New → Static Site**.
3. Connect the `Fitness-Tracker` GitHub repo.
4. Settings:
   - **Build command:** *(leave empty — there's nothing to build)*
   - **Publish directory:** `.` (repo root)
5. Click **Create Static Site**. Render will auto-deploy on every push to
   the connected branch.
6. Once deployed, Render gives you a URL serving this folder — open it and
   log in the same way as local.

No environment variables are needed on Render: the Supabase project URL and
anon public key are embedded in the page (the anon key is meant to be
public; row-level security on the Supabase tables is what actually
restricts access to your own data).
