import json
import requests
import streamlit as st

# Functie om NFTs op te halen via Helius DAS API (met pagination)
def get_nft_images(wallet_address: str, rpc_endpoint: str) -> list:
    api_key = rpc_endpoint.split('api-key=')[-1]  # Extract key from endpoint
    base_url = rpc_endpoint.split('?')[0]  # Base URL without key
    
    nfts = []
    unique_collections = {}  # Om collection mints te verzamelen en later names te fetchen
    page = 1
    while True:
        payload = {
            "jsonrpc": "2.0",
            "id": "helius-test",
            "method": "getAssetsByOwner",
            "params": {
                "ownerAddress": wallet_address,
                "page": page,
                "limit": 1000,
                "options": {"showFungible": False}
            }
        }
        
        try:
            response = requests.post(f"{base_url}?api-key={api_key}", json=payload)
            response.raise_for_status()
            data = response.json()
            
            if 'error' in data:
                return [{"error": f"API fout: {data['error']['message']}"}]
            
            items = data.get('result', {}).get('items', [])
            if not items:
                break
            
            for item in items:
                name = item.get('content', {}).get('metadata', {}).get('name', 'Onbekend')
                files = item.get('content', {}).get('files', [])
                image_url = next((f.get('uri') for f in files if f.get('mime', '').startswith('image/')), None)
                json_uri = item.get('content', {}).get('json_uri')
                
                # Fetch off-chain JSON voor image en rarity
                rarity_rank = 'N/A'  # Default
                if json_uri:
                    try:
                        json_resp = requests.get(json_uri)
                        if json_resp.status_code == 200:
                            offchain_data = json_resp.json()
                            if not image_url:
                                image_url = offchain_data.get('image')
                            # Haal rarity rank
                            attributes = offchain_data.get('attributes', [])
                            for attr in attributes:
                                if attr.get('trait_type') == 'Rarity Rank':
                                    rarity_rank = attr.get('value')
                                    break
                    except:
                        pass
                
                collection_mint = 'None'
                if 'grouping' in item:
                    for group in item['grouping']:
                        if group['group_key'] == 'collection':
                            collection_mint = group['group_value']
                            unique_collections[collection_mint] = None
                            break
                
                nfts.append({
                    "name": name,
                    "image_url": image_url or "Geen afbeelding beschikbaar",
                    "mint": item.get('id', 'Onbekend'),
                    "collection_mint": collection_mint,
                    "rarity_rank": rarity_rank
                })
            
            if len(items) < 1000:
                break
            page += 1
        
        except Exception as e:
            return [{"error": f"Fout bij ophalen: {str(e)}"}]
    
    # Fetch collection names
    for mint in unique_collections:
        if mint != 'None':
            payload = {
                "jsonrpc": "2.0",
                "id": "helius-coll-name",
                "method": "getAsset",
                "params": {"id": mint}
            }
            response = requests.post(f"{base_url}?api-key={api_key}", json=payload)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    unique_collections[mint] = data['result'].get('content', {}).get('metadata', {}).get('name', mint)
    
    # Update NFTs met collection names
    for nft in nfts:
        mint = nft['collection_mint']
        nft['collection'] = unique_collections.get(mint, 'Uncategorized') if mint != 'None' else 'Uncategorized'
    
    if not nfts:
        return [{"error": "Geen NFTs gevonden"}]
    
    return nfts

# Streamlit app
def main():
    st.title("Solana NFT Viewer")
    
    wallet_address = st.text_input("Voer Solana wallet adres in:", "YXWkcPEu7XeZDhwAnc357Pzr8Ck3Up7tqN6odX69ZRW")
    
    # Hardcoded naar mainnet (selectie verwijderd)
    rpc_endpoint = "https://mainnet.helius-rpc.com/?api-key=b59a909b-38fe-492e-b699-6668bb25efa5"
    
    if st.button("Toon NFTs"):
        if wallet_address:
            with st.spinner("NFTs ophalen..."):
                nfts = get_nft_images(wallet_address, rpc_endpoint)
                
                if nfts and "error" in nfts[0]:
                    st.error(nfts[0]["error"])
                elif nfts:
                    st.success(f"Gevonden {len(nfts)} NFTs!")
                    
                    from collections import defaultdict
                    grouped_nfts = defaultdict(list)
                    for nft in nfts:
                        grouped_nfts[nft['collection']].append(nft)
                    
                    for collection, items in grouped_nfts.items():
                        st.header(collection)
                        
                        # Sorteer op rarity_rank ascending (meest rare eerst, assuming lower = rarer)
                        # Handle non-numeric ranks en fractions (bijv. '123/5000' → 123)
                        def rank_key(x):
                            rank = x['rarity_rank']
                            if isinstance(rank, int):
                                return rank
                            elif isinstance(rank, str):
                                # Neem eerste numerieke deel (bijv. '123/5000' → 123)
                                numeric_part = ''.join(c for c in rank if c.isdigit())
                                if numeric_part:
                                    return int(numeric_part)
                            return 999999  # Fallback voor N/A of invalid
                        
                        sorted_items = sorted(items, key=rank_key)
                        
                        cols = st.columns(4)
                        for idx, nft in enumerate(sorted_items):
                            with cols[idx % 4]:
                                if nft['image_url'] != "Geen afbeelding beschikbaar":
                                    st.markdown(
                                        f'<a href="{nft["image_url"]}" target="_blank"><img src="{nft["image_url"]}" width="150"></a>',
                                        unsafe_allow_html=True
                                    )
                                else:
                                    st.write("Geen afbeelding")
                                st.caption(nft['name'])
                                st.write(f"Rarity Rank: {nft['rarity_rank']}")
                else:
                    st.error("Geen NFTs gevonden of er is een fout opgetreden.")
        else:
            st.warning("Voer een wallet adres in.")

if __name__ == "__main__":
    main()