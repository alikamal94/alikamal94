//+------------------------------------------------------------------+
//|                                                  ORB_NY_EA.mq5   |
//|                                                  © alikamal94    |
//|                                                                  |
//| New York Opening Range Breakout + Retest — Expert Advisor (MT5)  |
//|  1) Builds the NY opening range (09:30 NY) over 1, 5 or 15 min   |
//|     from M1 data.                                                |
//|  2) Waits for a candle CLOSE through the ORB High, ORB Low or    |
//|     the 50% level.                                               |
//|  3) Enters on the retest when it is confirmed by a Fair Value    |
//|     Gap, a level (High/Low) retest or a strong rejection candle. |
//|  Same rules as the "ORB NY" TradingView indicator.               |
//|  All signals are evaluated on CLOSED candles only.               |
//+------------------------------------------------------------------+
#property copyright "© alikamal94"
#property version   "1.00"
#property description "New York Opening Range Breakout + Retest EA (FVG / level retest / rejection candle confirmation)."

#include <Trade/Trade.mqh>

//--- enums
enum ENUM_TZ_MODE
  {
   TZ_NY_CLOSE  = 0, // Broker follows NY close (GMT+2/+3) - fixed offset
   TZ_FIXED_GMT = 1  // Broker is fixed GMT+N (no daylight saving)
  };

enum ENUM_ORB_MIN
  {
   ORB_AUTO = 0,  // Auto (= signal timeframe if 1/5/15 min, else 15)
   ORB_1    = 1,  // 1 minute
   ORB_5    = 5,  // 5 minutes
   ORB_15   = 15  // 15 minutes
  };

enum ENUM_SL_MODE
  {
   SL_RETEST   = 0, // Beyond the retest candles
   SL_OPPOSITE = 1, // Opposite ORB side (ORB High for shorts / ORB Low for longs)
   SL_MID      = 2  // ORB 50% level
  };

enum ENUM_ENTRY_MODE
  {
   ENTRY_MARKET = 0, // Market order at the confirmation candle close
   ENTRY_LIMIT  = 1  // Limit order at the retest level (FVG edge for FVG entries)
  };

enum ENUM_LOT_MODE
  {
   LOT_RISK_PCT = 0, // Risk % of equity
   LOT_FIXED    = 1  // Fixed lots
  };

//--- inputs
input group "Session (New York time)"
input ENUM_TZ_MODE InpTZMode        = TZ_NY_CLOSE; // Broker server time zone
input int          InpServerMinusNY = 7;           // Server time minus NY time, hours (NY-close brokers = 7)
input int          InpBrokerGMT     = 0;           // Broker GMT offset (only for "fixed GMT+N")
input int          InpOpenHour      = 9;           // NY open hour
input int          InpOpenMin       = 30;          // NY open minute
input int          InpSigEndHour    = 12;          // Stop new signals at (NY hour)
input int          InpSigEndMin     = 0;           // Stop new signals at (NY minute)
input bool         InpCloseAtEnd    = true;        // Close open trades at session end
input int          InpCloseHour     = 16;          // Session end (NY hour)
input int          InpCloseMin      = 0;           // Session end (NY minute)

input group "Opening range & breakout"
input ENUM_TIMEFRAMES InpTF       = PERIOD_M5; // Signal timeframe
input ENUM_ORB_MIN    InpORB      = ORB_AUTO;  // Opening range length
input bool            InpUseHL    = true;      // Trade ORB High / Low breakouts
input bool            InpUseMid   = true;      // Trade 50% level breakouts
input double          InpTolATR   = 0.25;      // Retest tolerance (x ATR14)
input int             InpMaxWait  = 30;        // Max bars to wait for the retest
input int             InpMaxTrades= 1;         // Max trades per session

input group "Entry confirmation (any enabled one confirms)"
input bool   InpConfFVG   = true; // Fair Value Gap retest
input bool   InpConfLevel = true; // High / Low level retest
input bool   InpConfRej   = true; // Strong rejection candle (pin bar / engulfing)
input double InpWickPct   = 0.5;  // Rejection: min wick as fraction of candle

input group "Risk & orders"
input ENUM_ENTRY_MODE InpEntry      = ENTRY_MARKET; // Entry type
input int             InpLimitBars  = 10;           // Limit order: cancel after N bars
input ENUM_SL_MODE    InpSLMode     = SL_RETEST;    // Stop loss
input double          InpSLBufATR   = 0.1;          // SL buffer (x ATR14)
input double          InpRR         = 2.0;          // Take profit (R multiple)
input ENUM_LOT_MODE   InpLotMode    = LOT_RISK_PCT; // Position sizing
input double          InpRiskPct    = 1.0;          // Risk per trade (% of equity)
input double          InpFixedLots  = 0.10;         // Fixed lots
input double          InpBEatR      = 0.0;          // Move SL to break-even at +R (0 = off)
input int             InpMaxSpread  = 0;            // Max spread in points (0 = off)
input int             InpSlippage   = 20;           // Max slippage (points)

input group "Misc"
input long InpMagic = 94093001; // Magic number
input bool InpDraw  = true;     // Draw ORB levels and signals on the chart

//--- colours (same as the indicator)
#define C_ENTRY  clrRoyalBlue
#define C_SL     clrRed
#define C_TP     clrLimeGreen
#define C_BRK    clrDarkViolet

//--- globals
CTrade   trade;
int      atrHandle = INVALID_HANDLE;
string   PFX       = "ORBEA_";

datetime gDayNY    = 0;   // NY midnight of the current session (NY clock)
datetime gSessStart= 0;   // server time
datetime gOrbEnd   = 0;   // server time
datetime gSigEnd   = 0;   // server time
datetime gCloseT   = 0;   // server time
double   gHi = 0, gLo = 0;
bool     gReady    = false;

int      gState    = 0;   // 0 watching, 1 waiting for retest, 2 order/position active
int      gDir      = 0;
double   gLvl      = 0;
string   gLvlName  = "";
int      gWait     = 0;
int      gTrades   = 0;
bool     gFvg      = false;
double   gFvgTop   = 0, gFvgBot = 0;
datetime gFvgTime  = 0;
int      gPendBars = 0;
double   gRisk     = 0;
bool     gBEdone   = false;
datetime gLastBar  = 0;
string   gLastMsg  = "";

//+------------------------------------------------------------------+
//| Helpers                                                          |
//+------------------------------------------------------------------+
ENUM_TIMEFRAMES TF()
  {
   return InpTF == PERIOD_CURRENT ? (ENUM_TIMEFRAMES)_Period : InpTF;
  }

int ORBMinutes()
  {
   if(InpORB != ORB_AUTO)
      return (int)InpORB;
   int m = PeriodSeconds(TF()) / 60;
   return (m == 1 || m == 5 || m == 15) ? m : 15;
  }

// Date of the n-th Sunday of a month at 02:00
datetime NthSunday(int year, int mon, int n)
  {
   MqlDateTime s;
   ZeroMemory(s);
   s.year = year; s.mon = mon; s.day = 1;
   datetime first = StructToTime(s);
   TimeToStruct(first, s);
   int firstSun = 1 + (7 - s.day_of_week) % 7;
   s.day  = firstSun + 7 * (n - 1);
   s.hour = 2; s.min = 0; s.sec = 0;
   return StructToTime(s);
  }

// US daylight saving: 2nd Sunday of March -> 1st Sunday of November
bool IsUSDST(datetime nyStd)
  {
   MqlDateTime d;
   TimeToStruct(nyStd, d);
   return nyStd >= NthSunday(d.year, 3, 2) && nyStd < NthSunday(d.year, 11, 1);
  }

int ServerMinusNY(datetime srv)
  {
   if(InpTZMode == TZ_NY_CLOSE)
      return InpServerMinusNY;
   datetime utc   = srv - InpBrokerGMT * 3600;
   datetime nyStd = utc - 5 * 3600;
   int nyOffset   = IsUSDST(nyStd) ? -4 : -5;
   return InpBrokerGMT - nyOffset;
  }

double NormPrice(double p)
  {
   double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(ts <= 0) ts = _Point;
   return NormalizeDouble(MathRound(p / ts) * ts, _Digits);
  }

bool HasPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         return true;
     }
   return false;
  }

bool HasOrder()
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t > 0 && OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == InpMagic)
         return true;
     }
   return false;
  }

void CloseAll()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic)
         trade.PositionClose(t);
     }
  }

void DeleteOrders()
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t > 0 && OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == InpMagic)
         trade.OrderDelete(t);
     }
  }

bool CanDraw()
  {
   if(!InpDraw) return false;
   if(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE)) return false;
   return true;
  }

void DrawLine(string name, datetime t1, double p, datetime t2, color c, ENUM_LINE_STYLE st, int w)
  {
   if(!CanDraw()) return;
   string n = PFX + name;
   if(ObjectFind(0, n) >= 0) return;            // drawn once, never moved
   ObjectCreate(0, n, OBJ_TREND, 0, t1, p, t2, p);
   ObjectSetInteger(0, n, OBJPROP_COLOR, c);
   ObjectSetInteger(0, n, OBJPROP_STYLE, st);
   ObjectSetInteger(0, n, OBJPROP_WIDTH, w);
   ObjectSetInteger(0, n, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, n, OBJPROP_BACK, true);
  }

void DrawText(string name, datetime t, double p, string txt, color c, ENUM_ANCHOR_POINT anchor)
  {
   if(!CanDraw()) return;
   string n = PFX + name;
   if(ObjectFind(0, n) >= 0) return;
   ObjectCreate(0, n, OBJ_TEXT, 0, t, p);
   ObjectSetString(0, n, OBJPROP_TEXT, txt);
   ObjectSetInteger(0, n, OBJPROP_COLOR, c);
   ObjectSetInteger(0, n, OBJPROP_FONTSIZE, 8);
   ObjectSetInteger(0, n, OBJPROP_ANCHOR, anchor);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
  }

void DrawArrow(string name, datetime t, double p, bool buy)
  {
   if(!CanDraw()) return;
   string n = PFX + name;
   if(ObjectFind(0, n) >= 0) return;
   ObjectCreate(0, n, buy ? OBJ_ARROW_BUY : OBJ_ARROW_SELL, 0, t, p);
   ObjectSetInteger(0, n, OBJPROP_COLOR, buy ? C_TP : C_SL);
   ObjectSetInteger(0, n, OBJPROP_WIDTH, 2);
   ObjectSetInteger(0, n, OBJPROP_SELECTABLE, false);
  }

string Px(double p) { return DoubleToString(p, _Digits); }

//+------------------------------------------------------------------+
//| Session / day handling                                           |
//+------------------------------------------------------------------+
void DayCheck()
  {
   datetime now = TimeCurrent();
   int      off = ServerMinusNY(now);
   datetime ny  = now - off * 3600;
   MqlDateTime d;
   TimeToStruct(ny, d);
   d.hour = 0; d.min = 0; d.sec = 0;
   datetime nyMid = StructToTime(d);
   if(nyMid == gDayNY)
      return;

   gDayNY     = nyMid;
   gSessStart = nyMid + InpOpenHour   * 3600 + InpOpenMin   * 60 + off * 3600;
   gOrbEnd    = gSessStart + ORBMinutes() * 60;
   gSigEnd    = nyMid + InpSigEndHour * 3600 + InpSigEndMin * 60 + off * 3600;
   gCloseT    = nyMid + InpCloseHour  * 3600 + InpCloseMin  * 60 + off * 3600;
   gReady     = false;
   gTrades    = 0;
   gFvg       = false;
   if(!HasPosition() && !HasOrder())
      gState = 0;
  }

// Build the opening range from M1 bars once the window has fully closed
void BuildORB()
  {
   if(gReady || TimeCurrent() < gOrbEnd)
      return;
   MqlRates r[];
   int n = CopyRates(_Symbol, PERIOD_M1, gSessStart, gOrbEnd - 1, r);
   if(n <= 0)
      return;
   double hi = -DBL_MAX, lo = DBL_MAX;
   int used = 0;
   for(int i = 0; i < n; i++)
     {
      if(r[i].time < gSessStart || r[i].time >= gOrbEnd) continue;
      hi = MathMax(hi, r[i].high);
      lo = MathMin(lo, r[i].low);
      used++;
     }
   if(used == 0)
      return;
   gHi    = hi;
   gLo    = lo;
   gReady = true;

   string day = TimeToString(gDayNY, TIME_DATE);
   double mid = (gHi + gLo) / 2;
   DrawLine("hi_"  + day, gSessStart, gHi, gCloseT, C_BRK, STYLE_SOLID, 2);
   DrawLine("lo_"  + day, gSessStart, gLo, gCloseT, C_BRK, STYLE_SOLID, 2);
   DrawLine("mid_" + day, gSessStart, mid, gCloseT, C_BRK, STYLE_DOT,   1);
   DrawText("lbl_" + day, gSessStart, gHi, IntegerToString(ORBMinutes()) + "m ORB", C_BRK, ANCHOR_LEFT_LOWER);
   gLastMsg = StringFormat("%dm ORB ready  H %s  L %s", ORBMinutes(), Px(gHi), Px(gLo));
  }

//+------------------------------------------------------------------+
//| Position sizing                                                  |
//+------------------------------------------------------------------+
double CalcLots(double entry, double sl)
  {
   double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lots = InpFixedLots;

   if(InpLotMode == LOT_RISK_PCT)
     {
      double loss = 0;
      ENUM_ORDER_TYPE ot = gDir == 1 ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
      if(!OrderCalcProfit(ot, _Symbol, 1.0, entry, sl, loss) || loss >= 0)
        {
         double tv = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
         double ts = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
         if(tv <= 0 || ts <= 0) return 0;
         loss = -MathAbs(entry - sl) / ts * tv;
        }
      double money = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPct / 100.0;
      lots = money / MathAbs(loss);
     }

   if(step > 0) lots = MathFloor(lots / step) * step;
   if(lots < vmin)
     {
      Print("ORB EA: calculated lot size ", DoubleToString(lots, 4), " is below the broker minimum ", vmin, " - trade skipped.");
      return 0;
     }
   lots = MathMin(lots, vmax);
   int dg = (step > 0) ? (int)MathMax(0, MathCeil(-MathLog10(step))) : 2;
   return NormalizeDouble(lots, dg);
  }

//+------------------------------------------------------------------+
//| Entry                                                            |
//+------------------------------------------------------------------+
void Enter(const MqlRates &r[], double atr, string how)
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   bool   fvgOnly  = (how == "FVG retest");
   double lvlEntry = fvgOnly ? (gDir == 1 ? gFvgTop : gFvgBot) : gLvl;
   bool   useLimit = InpEntry == ENTRY_LIMIT &&
                     ((gDir == 1 && lvlEntry < ask) || (gDir == -1 && lvlEntry > bid));
   // Too close to the current price for a pending order -> enter at market instead
   double stopsLvl = (double)SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   if(useLimit && MathAbs((gDir == 1 ? ask : bid) - lvlEntry) <= stopsLvl)
      useLimit = false;
   double entry    = useLimit ? lvlEntry : (gDir == 1 ? ask : bid);

   // Stop loss: LONG below the entry, SHORT above the entry
   double buf = atr * InpSLBufATR;
   double rl  = MathMin(MathMin(r[0].low,  r[1].low),  entry);
   double rh  = MathMax(MathMax(r[0].high, r[1].high), entry);
   double sl;
   switch(InpSLMode)
     {
      case SL_OPPOSITE: sl = gDir == 1 ? gLo - buf : gHi + buf; break;
      case SL_MID:      sl = gDir == 1 ? (gHi + gLo) / 2 - buf : (gHi + gLo) / 2 + buf; break;
      default:          sl = gDir == 1 ? rl - buf : rh + buf; break;
     }
   double risk = gDir == 1 ? entry - sl : sl - entry;
   if(risk <= 0)
     {
      sl   = gDir == 1 ? rl - buf : rh + buf;
      risk = gDir == 1 ? entry - sl : sl - entry;
     }
   if(risk <= 0)
     {
      risk = MathMax(atr * 0.5, _Point);
      sl   = entry - gDir * risk;
     }
   // Respect the broker's minimum stop distance
   if(risk < stopsLvl)
     {
      risk = stopsLvl;
      sl   = entry - gDir * risk;
     }

   // Take profit: LONG = entry + R x risk (above), SHORT = entry - R x risk (below)
   double tp = gDir == 1 ? entry + InpRR * risk : entry - InpRR * risk;

   entry = NormPrice(entry);
   sl    = NormPrice(sl);
   tp    = NormPrice(tp);

   double lots = CalcLots(entry, sl);
   if(lots <= 0)
     {
      gState = 0;
      return;
     }

   string cmt = "ORB " + (gLvlName == "ORB 50%" ? "50%" : (gDir == 1 ? "High" : "Low")) + " " + how;
   bool ok;
   if(useLimit)
      ok = gDir == 1 ? trade.BuyLimit(lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, cmt)
                     : trade.SellLimit(lots, entry, _Symbol, sl, tp, ORDER_TIME_GTC, 0, cmt);
   else
      ok = gDir == 1 ? trade.Buy(lots, _Symbol, 0, sl, tp, cmt)
                     : trade.Sell(lots, _Symbol, 0, sl, tp, cmt);

   if(!ok)
     {
      Print("ORB EA: order failed, retcode ", trade.ResultRetcode(), " ", trade.ResultRetcodeDescription());
      gState = 0;
      return;
     }

   gTrades++;
   gState    = 2;
   gPendBars = 0;
   gRisk     = risk;
   gBEdone   = false;

   datetime now = TimeCurrent();
   datetime t2  = now + 30 * PeriodSeconds(TF());
   string   id  = TimeToString(now, TIME_DATE | TIME_MINUTES);
   DrawArrow("sig_" + id, now, entry, gDir == 1);
   DrawLine("en_" + id, now, entry, t2, C_ENTRY, STYLE_SOLID, 2);
   DrawLine("sl_" + id, now, sl,    t2, C_SL,    STYLE_SOLID, 2);
   DrawLine("tp_" + id, now, tp,    t2, C_TP,    STYLE_SOLID, 2);
   DrawText("sigtx_" + id, now, sl, (gDir == 1 ? "LONG " : "SHORT ") + how, gDir == 1 ? C_TP : C_SL,
            gDir == 1 ? ANCHOR_LEFT_UPPER : ANCHOR_LEFT_LOWER);

   gLastMsg = StringFormat("%s %s @ %s  SL %s  TP %s  (%s, %.2f lots)%s",
                           gDir == 1 ? "LONG" : "SHORT", gLvlName, Px(entry), Px(sl), Px(tp), how, lots,
                           useLimit ? " [limit]" : "");
   Print("ORB EA: ", gLastMsg);
  }

//+------------------------------------------------------------------+
//| Signal logic on the last CLOSED candle                           |
//+------------------------------------------------------------------+
void OnNewBar()
  {
   MqlRates r[];
   ArraySetAsSeries(r, true);
   if(CopyRates(_Symbol, TF(), 1, 3, r) < 3)   // r[0] = last closed bar, r[1], r[2] = older
      return;
   double a[];
   if(CopyBuffer(atrHandle, 0, 1, 1, a) < 1)
      return;
   double   atr = a[0];
   double   tol = atr * InpTolATR;
   datetime t1  = r[0].time;

   // Pending limit order expiry
   if(gState == 2 && HasOrder())
     {
      gPendBars++;
      if(gPendBars > InpLimitBars || t1 >= gSigEnd)
        {
         DeleteOrders();
         gLastMsg = "Limit order expired";
        }
     }

   bool canSignal = gReady && t1 >= gOrbEnd && t1 < gSigEnd && gTrades < InpMaxTrades;

   //--- 1) Breakout detection
   if(gState == 0 && canSignal)
     {
      double md = (gHi + gLo) / 2;
      double c0 = r[0].close, c1 = r[1].close;
      int    d  = 0;
      double L  = 0;
      string n  = "";
      if(InpUseHL && c0 > gHi && c1 <= gHi)                    { d =  1; L = gHi; n = "ORB High"; }
      else if(InpUseHL && c0 < gLo && c1 >= gLo)               { d = -1; L = gLo; n = "ORB Low";  }
      else if(InpUseMid && c0 > md && c1 <= md && c0 <= gHi)   { d =  1; L = md;  n = "ORB 50%";  }
      else if(InpUseMid && c0 < md && c1 >= md && c0 >= gLo)   { d = -1; L = md;  n = "ORB 50%";  }
      if(d != 0)
        {
         gState   = 1;
         gDir     = d;
         gLvl     = L;
         gLvlName = n;
         gWait    = 0;
         gFvg     = false;
         DrawText("brk_" + TimeToString(t1, TIME_DATE | TIME_MINUTES), t1, d == 1 ? r[0].high : r[0].low,
                  (d == 1 ? "Break up " : "Break down ") + n, C_BRK, d == 1 ? ANCHOR_LOWER : ANCHOR_UPPER);
         gLastMsg = StringFormat("%s breakout of %s (%s) - waiting for retest", d == 1 ? "Bullish" : "Bearish", n, Px(L));
         Print("ORB EA: ", gLastMsg);
        }
     }
   //--- 2) Retest + confirmation
   else if(gState == 1)
     {
      gWait++;

      // First FVG left by the breakout move
      if(!gFvg)
        {
         if(gDir == 1 && r[0].low > r[2].high)
           { gFvg = true; gFvgTop = r[0].low;  gFvgBot = r[2].high; gFvgTime = t1; }
         else if(gDir == -1 && r[0].high < r[2].low)
           { gFvg = true; gFvgTop = r[2].low;  gFvgBot = r[0].high; gFvgTime = t1; }
        }

      double o = r[0].open, h = r[0].high, l = r[0].low, c = r[0].close;
      double rng       = h - l;
      bool   touchLvl  = gDir == 1 ? l <= gLvl + tol : h >= gLvl - tol;
      bool   hold      = gDir == 1 ? c > gLvl : c < gLvl;
      bool   dirCandle = gDir == 1 ? c > o : c < o;
      double wick      = gDir == 1 ? MathMin(o, c) - l : h - MathMax(o, c);
      double closePos  = rng > 0 ? (gDir == 1 ? c - l : h - c) / rng : 0.0;
      bool   pinBar    = rng > 0 && wick >= InpWickPct * rng && closePos >= 0.6;
      bool   engulf    = gDir == 1
                         ? (c > o && r[1].close < r[1].open && c >= r[1].open && o <= r[1].close)
                         : (c < o && r[1].close > r[1].open && c <= r[1].open && o >= r[1].close);
      bool   touchFVG  = gFvg && t1 > gFvgTime &&
                         (gDir == 1 ? (l <= gFvgTop && c > gFvgBot) : (h >= gFvgBot && c < gFvgTop));

      bool okFVG   = InpConfFVG   && touchFVG && hold && dirCandle;
      bool okRej   = InpConfRej   && touchLvl && hold && (pinBar || engulf);
      bool okLvl   = InpConfLevel && touchLvl && hold && dirCandle;
      bool invalid = gDir == 1 ? c < gLvl - tol : c > gLvl + tol;

      if(invalid || gWait > InpMaxWait || t1 >= gSigEnd)
        {
         gState = 0;
         gLastMsg = invalid ? "Breakout failed (closed back through the level)" : "No retest in time - setup cancelled";
         DrawText("x_" + TimeToString(t1, TIME_DATE | TIME_MINUTES), t1, gDir == 1 ? l : h,
                  invalid ? "x failed" : "x no retest", clrGray, gDir == 1 ? ANCHOR_UPPER : ANCHOR_LOWER);
        }
      else if(okFVG || okRej || okLvl)
        {
         string how = okRej ? (pinBar ? "Rejection wick" : "Engulfing") : okLvl ? "Level retest" : "FVG retest";
         if(InpMaxSpread > 0 && SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpMaxSpread)
           {
            gLastMsg = "Signal skipped: spread too high";
            Print("ORB EA: ", gLastMsg);
            return;   // keep waiting for another confirmation candle
           }
         Enter(r, atr, how);
        }
     }
  }

//+------------------------------------------------------------------+
//| Trade management (every tick)                                    |
//+------------------------------------------------------------------+
void Manage()
  {
   bool pos = HasPosition();
   bool ord = HasOrder();

   // Trade finished (TP / SL hit, or order cancelled) -> watch again if trades remain
   if(gState == 2 && !pos && !ord)
      gState = 0;

   // Session end
   if(InpCloseAtEnd && TimeCurrent() >= gCloseT && TimeCurrent() >= gSessStart)
     {
      if(pos) { CloseAll();     gLastMsg = "Session end - position closed"; }
      if(ord) { DeleteOrders(); }
     }

   // Break-even
   if(pos && InpBEatR > 0 && gRisk > 0 && !gBEdone)
     {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
        {
         ulong t = PositionGetTicket(i);
         if(t == 0 || PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic)
            continue;
         long   type  = PositionGetInteger(POSITION_TYPE);
         double open  = PositionGetDouble(POSITION_PRICE_OPEN);
         double sl    = PositionGetDouble(POSITION_SL);
         double tp    = PositionGetDouble(POSITION_TP);
         double price = type == POSITION_TYPE_BUY ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double prog  = type == POSITION_TYPE_BUY ? price - open : open - price;
         if(prog >= InpBEatR * gRisk)
           {
            bool better = type == POSITION_TYPE_BUY ? (sl < open) : (sl > open || sl == 0);
            if(better && trade.PositionModify(t, NormPrice(open), tp))
              {
               gBEdone  = true;
               gLastMsg = "Stop moved to break-even";
              }
           }
        }
     }
  }

//+------------------------------------------------------------------+
//| Status panel                                                     |
//+------------------------------------------------------------------+
void ShowStatus()
  {
   if(MQLInfoInteger(MQL_TESTER) && !MQLInfoInteger(MQL_VISUAL_MODE))
      return;
   string st;
   switch(gState)
     {
      case 1:  st = (gDir == 1 ? "Up " : "Down ") + gLvlName + " broken - waiting for retest"; break;
      case 2:  st = HasOrder() ? "Limit order working" : "In trade"; break;
      default: st = gTrades >= InpMaxTrades ? "Session locked" : "Watching for breakout";
     }
   string orb = gReady ? StringFormat("H %s | 50%% %s | L %s", Px(gHi), Px((gHi + gLo) / 2), Px(gLo)) : "building / waiting for 09:30 NY";
   Comment(StringFormat("ORB NY EA  (%dm ORB, %s signals)\nORB: %s\nStatus: %s  (%d/%d trades)\nLast: %s",
                        ORBMinutes(), EnumToString(TF()), orb, st, gTrades, InpMaxTrades, gLastMsg));
  }

//+------------------------------------------------------------------+
//| Expert events                                                    |
//+------------------------------------------------------------------+
int OnInit()
  {
   if(InpRR <= 0 || InpRiskPct <= 0 || InpMaxTrades < 1)
     {
      Print("ORB EA: invalid inputs.");
      return INIT_PARAMETERS_INCORRECT;
     }
   atrHandle = iATR(_Symbol, TF(), 14);
   if(atrHandle == INVALID_HANDLE)
     {
      Print("ORB EA: cannot create ATR handle.");
      return INIT_FAILED;
     }
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetDeviationInPoints(InpSlippage);
   trade.SetTypeFillingBySymbol(_Symbol);

   if(PeriodSeconds(TF()) > ORBMinutes() * 60)
      Print("ORB EA: note - signal timeframe is larger than the opening range, the first breakout candle starts later.");

   // A restart mid-session: pick up any open position / order of this EA
   if(HasPosition() || HasOrder())
      gState = 2;
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   if(atrHandle != INVALID_HANDLE)
      IndicatorRelease(atrHandle);
   Comment("");
   if(reason == REASON_REMOVE)
      ObjectsDeleteAll(0, PFX);
  }

void OnTick()
  {
   DayCheck();
   BuildORB();
   Manage();

   datetime bt = iTime(_Symbol, TF(), 0);
   if(bt != gLastBar)
     {
      if(gLastBar != 0)
         OnNewBar();
      gLastBar = bt;
     }
   ShowStatus();
  }
//+------------------------------------------------------------------+
