//====================================================================
// Signal buffers — the armed setup exposed to EAs via iCustom/CopyBuffer.
//
// One value per *closed* bar (the forming bar copies the last closed bar).
// Plots are DRAW_NONE, so nothing is drawn; values show in the Data Window.
//
//   0 Entry   1 SL   2 TP1   3 TP2   4 TP3   (EMPTY_VALUE when no setup)
//   5 Direction : +1 buy, -1 sell, 0 none
//   6 State     : 1 TRACKING (armed), 2 TP1_HIT, -1 INVALIDATED, 0 IDLE
//   7 Armed     : 1 on the bar the setup was armed, else 0
//
// EA example (read the last closed bar, shift 1):
//   int h=iCustom(_Symbol,_Period,"ICT_Assistant_Canonical_v0_1");
//   double armed[1]; CopyBuffer(h,SIGBUF_ARMED,1,1,armed);
//====================================================================
#define SIGBUF_ENTRY 0
#define SIGBUF_SL    1
#define SIGBUF_TP1   2
#define SIGBUF_TP2   3
#define SIGBUF_TP3   4
#define SIGBUF_DIR   5
#define SIGBUF_STATE 6
#define SIGBUF_ARMED 7
#define SIGBUF_COUNT 8

double g_bufEntry[], g_bufSL[], g_bufTP1[], g_bufTP2[], g_bufTP3[];
double g_bufDir[], g_bufState[], g_bufArmed[];

void InitSignalBuffers()
{
   SetIndexBuffer(SIGBUF_ENTRY, g_bufEntry, INDICATOR_DATA);
   SetIndexBuffer(SIGBUF_SL,    g_bufSL,    INDICATOR_DATA);
   SetIndexBuffer(SIGBUF_TP1,   g_bufTP1,   INDICATOR_DATA);
   SetIndexBuffer(SIGBUF_TP2,   g_bufTP2,   INDICATOR_DATA);
   SetIndexBuffer(SIGBUF_TP3,   g_bufTP3,   INDICATOR_DATA);
   SetIndexBuffer(SIGBUF_DIR,   g_bufDir,   INDICATOR_DATA);
   SetIndexBuffer(SIGBUF_STATE, g_bufState, INDICATOR_DATA);
   SetIndexBuffer(SIGBUF_ARMED, g_bufArmed, INDICATOR_DATA);
   string labels[SIGBUF_COUNT]={"Setup Entry","Setup SL","Setup TP1","Setup TP2","Setup TP3",
                                "Setup Dir","Setup State","Setup Armed"};
   for(int i=0;i<SIGBUF_COUNT;i++)
   {
      PlotIndexSetInteger(i, PLOT_DRAW_TYPE, DRAW_NONE);
      PlotIndexSetDouble(i, PLOT_EMPTY_VALUE, EMPTY_VALUE);
      PlotIndexSetString(i, PLOT_LABEL, labels[i]);
   }
}

void SetSignalBuffersSeries(bool asSeries)
{
   ArraySetAsSeries(g_bufEntry,asSeries); ArraySetAsSeries(g_bufSL,asSeries);
   ArraySetAsSeries(g_bufTP1,asSeries);   ArraySetAsSeries(g_bufTP2,asSeries);
   ArraySetAsSeries(g_bufTP3,asSeries);   ArraySetAsSeries(g_bufDir,asSeries);
   ArraySetAsSeries(g_bufState,asSeries); ArraySetAsSeries(g_bufArmed,asSeries);
}

void ClearSignalBuffers()
{
   ArrayInitialize(g_bufEntry,EMPTY_VALUE); ArrayInitialize(g_bufSL,EMPTY_VALUE);
   ArrayInitialize(g_bufTP1,EMPTY_VALUE);   ArrayInitialize(g_bufTP2,EMPTY_VALUE);
   ArrayInitialize(g_bufTP3,EMPTY_VALUE);   ArrayInitialize(g_bufDir,0.0);
   ArrayInitialize(g_bufState,0.0);         ArrayInitialize(g_bufArmed,0.0);
}

double SetupLifeStateCode()
{
   if(g_setupLifeState=="TRACKING")    return 1.0;
   if(g_setupLifeState=="TP1_HIT")     return 2.0;
   if(g_setupLifeState=="INVALIDATED") return -1.0;
   return 0.0;
}

// Writes the lifecycle state as of closed bar barT into buffer index idx.
void WriteSignalBufferBar(int idx, datetime barT)
{
   if(idx<0 || idx>=ArraySize(g_bufEntry)) return;
   double st=SetupLifeStateCode();
   bool has=(st!=0.0);
   g_bufEntry[idx]=has? g_setupLifeEntry : EMPTY_VALUE;
   g_bufSL[idx]   =has? g_setupLifeSL    : EMPTY_VALUE;
   g_bufTP1[idx]  =has? g_setupLifeTP1   : EMPTY_VALUE;
   g_bufTP2[idx]  =(has && g_setupLifeTP2>0.0)? g_setupLifeTP2 : EMPTY_VALUE;
   g_bufTP3[idx]  =(has && g_setupLifeTP3>0.0)? g_setupLifeTP3 : EMPTY_VALUE;
   g_bufDir[idx]  =!has? 0.0 : (g_setupLifeDir==DIR_BULL? 1.0 : (g_setupLifeDir==DIR_BEAR? -1.0 : 0.0));
   g_bufState[idx]=st;
   g_bufArmed[idx]=(st==1.0 && g_setupLifeArmTime==barT)? 1.0 : 0.0;
}

// The forming bar mirrors the last closed bar, except the one-bar Armed pulse.
void CopySignalBufferBar(int from, int to)
{
   int n=ArraySize(g_bufEntry);
   if(from<0 || from>=n || to<0 || to>=n) return;
   g_bufEntry[to]=g_bufEntry[from]; g_bufSL[to]=g_bufSL[from];
   g_bufTP1[to]=g_bufTP1[from];     g_bufTP2[to]=g_bufTP2[from];
   g_bufTP3[to]=g_bufTP3[from];     g_bufDir[to]=g_bufDir[from];
   g_bufState[to]=g_bufState[from]; g_bufArmed[to]=0.0;
}
