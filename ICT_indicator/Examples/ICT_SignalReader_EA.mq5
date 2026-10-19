//+------------------------------------------------------------------+
//| ICT_SignalReader_EA.mq5                                          |
//| Example: read the ICT Assistant setup buffers and print a line   |
//| when a new setup is armed. Places no orders.                     |
//+------------------------------------------------------------------+
#property version "1.00"

input string InpIndicatorPath = "ICT_Assistant_Canonical_v0_1"; // path under MQL5\Indicators (e.g. "ICT\\ICT_Assistant_Canonical_v0_1")

// Buffer indices — must match modules/34_SignalBuffers.mqh
#define SIGBUF_ENTRY 0
#define SIGBUF_SL    1
#define SIGBUF_TP1   2
#define SIGBUF_TP2   3
#define SIGBUF_TP3   4
#define SIGBUF_DIR   5
#define SIGBUF_STATE 6
#define SIGBUF_ARMED 7

int      g_ict=INVALID_HANDLE;
datetime g_lastBar=0;

int OnInit()
{
   g_ict=iCustom(_Symbol,_Period,InpIndicatorPath);
   if(g_ict==INVALID_HANDLE)
   {
      Print("ICT reader | iCustom failed, error ",GetLastError());
      return INIT_FAILED;
   }
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   if(g_ict!=INVALID_HANDLE) IndicatorRelease(g_ict);
}

double ReadBuf(int buffer, int shift)
{
   double v[1];
   if(CopyBuffer(g_ict,buffer,shift,1,v)!=1) return EMPTY_VALUE;
   return v[0];
}

void OnTick()
{
   datetime bar=iTime(_Symbol,_Period,0);
   if(bar==g_lastBar) return;          // once per new bar
   g_lastBar=bar;

   // shift 1 = last closed bar
   if(ReadBuf(SIGBUF_ARMED,1)!=1.0) return;

   double dir  =ReadBuf(SIGBUF_DIR,1);
   double entry=ReadBuf(SIGBUF_ENTRY,1);
   double sl   =ReadBuf(SIGBUF_SL,1);
   double tp1  =ReadBuf(SIGBUF_TP1,1);
   double tp2  =ReadBuf(SIGBUF_TP2,1);
   double tp3  =ReadBuf(SIGBUF_TP3,1);
   PrintFormat("ICT setup ARMED %s | entry %s | SL %s | TP1 %s | TP2 %s | TP3 %s",
               dir>0?"BUY":"SELL", DoubleToString(entry,_Digits), DoubleToString(sl,_Digits),
               DoubleToString(tp1,_Digits),
               tp2==EMPTY_VALUE?"-":DoubleToString(tp2,_Digits),
               tp3==EMPTY_VALUE?"-":DoubleToString(tp3,_Digits));
   // Your order logic goes here (e.g. CTrade.BuyLimit at entry with sl/tp1).
}
