import os


def handler(request):
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json", "Cache-Control": "no-store"},
        "body": (
            '{"supabaseUrl":"%s","supabaseAnonKey":"%s"}'
            % (os.environ.get("SUPABASE_URL", ""), os.environ.get("SUPABASE_ANON_KEY", ""))
        ),
    }
