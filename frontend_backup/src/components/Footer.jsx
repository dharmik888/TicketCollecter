import React from 'react';
import { ShieldCheck, Lock, CheckCircle2 } from 'lucide-react';

export function Footer() {
  return (
    <footer style={{ backgroundColor: 'var(--bg-secondary)', borderTop: '1px solid var(--border-color)', marginTop: 'auto', padding: '40px 0 24px 0' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '0 24px' }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', alignItems: 'center', gap: '20px', paddingBottom: '24px', borderBottom: '1px solid var(--border-color)' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontWeight: 700, fontSize: '16px', color: 'var(--text-primary)' }}>
              <span>Fair<span style={{ color: 'var(--accent-primary)' }}>Drop</span></span>
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
              Transparent, bot-resistant ticket distribution platform.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '24px', fontSize: '13px', color: 'var(--text-secondary)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <ShieldCheck size={16} style={{ color: 'var(--success)' }} /> Cryptographic Proof-of-Work
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Lock size={15} style={{ color: 'var(--accent-primary)' }} /> Secure Session Lock
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CheckCircle2 size={16} style={{ color: 'var(--success)' }} /> Fair Allocation
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '20px', fontSize: '12px', color: 'var(--text-secondary)' }}>
          <div>© {new Date().getFullYear()} FairDrop Technologies Inc. All rights reserved.</div>
          <div style={{ display: 'flex', gap: '16px' }}>
            <span>Privacy Policy</span>
            <span>Terms of Service</span>
            <span>Security Whitepaper</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
