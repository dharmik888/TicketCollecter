// Web Crypto API based SHA-256
export async function sha256(message: string): Promise<string> {
  const msgBuffer = new TextEncoder().encode(message);                    
  const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  return hashHex;
}

export async function solvePoW(challenge: string, difficulty: number, onProgress: (nonce: number) => void): Promise<number> {
  const target = '0'.repeat(difficulty);
  let nonce = 0;
  
  return new Promise((resolve) => {
    // Process in chunks so we don't freeze the main thread
    const processChunk = async () => {
      for (let i = 0; i < 500; i++) {
        const hash = await sha256(challenge + nonce);
        if (hash.startsWith(target)) {
          resolve(nonce);
          return;
        }
        nonce++;
      }
      
      onProgress(nonce);
      // Yield to the browser
      setTimeout(processChunk, 0);
    };
    
    processChunk();
  });
}
