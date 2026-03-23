/* eslint-disable @next/next/no-page-custom-font */
export default function LearnLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=DM+Mono:wght@300;400;500&display=swap');
        .font-cormorant { font-family: 'Cormorant Garamond', serif; }
        .font-mono-dm   { font-family: 'DM Mono', monospace; }
      `}</style>
      {children}
    </>
  )
}
