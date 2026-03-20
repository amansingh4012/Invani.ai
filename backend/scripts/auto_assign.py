import os
import sys

# Add backend directory to sys.path to import settings securely
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import settings
from supabase import create_client

def auto_assign():
    print("Setting up Supabase connection...")
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        print("Error: Supabase Service Role Key is missing in .env")
        sys.exit(1)
        
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    
    print("Fetching businesses from database...")
    response = supabase.table("businesses").select("*").execute()
    
    businesses = response.data
    if not businesses:
        print("Error: No businesses found in the database. Are you sure you have created one?")
        sys.exit(1)
        
    for idx, b in enumerate(businesses):
        print(f"[{idx}] Business ID: {b.get('id')} | Name: {b.get('name')} | Phone: {b.get('phone_number')}")
        
    # Pick the first one (most common for single-user dev environments)
    target_business = businesses[0]
    target_id = target_business['id']
    
    print(f"\nAutomatically selecting Business '{target_business.get('name')}' with UUID {target_id}")
    
    # 1. Update the business
    EXOTEL_NUMBER = '+9108047361419'
    print(f"Assigning {EXOTEL_NUMBER} to Business {target_id}...")
    
    update_res = supabase.table("businesses").update({
        "phone_number": EXOTEL_NUMBER
    }).eq("id", target_id).execute()
    
    if not update_res.data:
        print("Failed to update business.")
        sys.exit(1)
        
    print("Business updated successfully!")
    
    # 2. Update the number pool (if the table exists and the pool number is there)
    try:
        pool_res = supabase.table("number_pool").update({
            "is_assigned": True,
            "assigned_to": target_id
        }).eq("phone_number", EXOTEL_NUMBER).execute()
        
        if not pool_res.data:
            print(f"Warning: Failed to update number_pool for {EXOTEL_NUMBER}. You might not have run the SQL script yet.")
        else:
            print("Number pool record updated successfully!")
    except Exception as e:
        print(f"Number pool update skipped: {e}")
        
    print("\n==============================================")
    print(" SUCCESS ")
    print("==============================================")
    print(f"Your True Business UUID is: {target_id}")
    print(f"Your AI Number is: {EXOTEL_NUMBER}")
    print("----------------------------------------------")
    print("IMPORTANT: Put this UUID into your frontend/.env file as VITE_BUSINESS_ID.")

if __name__ == "__main__":
    auto_assign()
