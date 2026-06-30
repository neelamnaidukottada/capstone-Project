#!/usr/bin/env python3
"""Verify campaigns are stored in Supabase database."""

import os
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv()

from app.core.supabase_client import get_supabase_admin_client

def verify_campaigns():
    """Check campaigns table in Supabase."""
    try:
        admin = get_supabase_admin_client()
        
        # Query all campaigns
        response = admin.table("campaigns").select("*").execute()
        campaigns = response.data or []
        
        print(f"✅ Connected to Supabase successfully!")
        print(f"\n📊 Total campaigns in database: {len(campaigns)}")
        
        if campaigns:
            print("\n📋 Campaign Details:")
            print("-" * 100)
            for i, campaign in enumerate(campaigns, 1):
                campaign_id = campaign.get("id")
                name = campaign.get("name") or "Untitled Campaign"
                status = campaign.get("status")
                pending_approval = campaign.get("pending_approval")
                created_at = campaign.get("created_at")
                updated_at = campaign.get("updated_at")
                
                print(f"\n{i}. Campaign ID: {campaign_id}")
                print(f"   Name: {name}")
                print(f"   Status: {status}")
                print(f"   Pending Approval: {pending_approval}")
                print(f"   Created: {created_at}")
                print(f"   Updated: {updated_at}")
        else:
            print("\n⚠️  No campaigns found in database")
            print("\nTo create a campaign:")
            print("1. Go to http://localhost:3000")
            print("2. Navigate to Dashboard")
            print("3. Click 'Create New Campaign'")
            print("4. Fill in campaign details and submit")
        
        print("\n" + "-" * 100)
        print("\n✅ Supabase verification complete!")
        
    except Exception as e:
        print(f"❌ Error connecting to Supabase: {str(e)}")
        print("\nMake sure your .env file has:")
        print("  - SUPABASE_URL")
        print("  - SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)

if __name__ == "__main__":
    verify_campaigns()
