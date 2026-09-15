# sqltypes_td.h — Teradata SQL Type Definitions for C UDFs

```c
#ifndef _SQLTYPES_TD_
#define _SQLTYPES_TD_
/**********************************************************************
Name:        sqltypes_td.h

   Copyright (c) 2001-2006 by NCR Corporation. 
   All Rights Reserved. 

Description: Defines the SQL data type in their equivalent C formats.

History:
         DR48360-CA3-01   01Apr20   Initial implementation
         DR59022-RGS-01   02Jun07   Add malloc/free
         DR60086-jbc-01   02May06   Added LOB support
         DR66509-jbc-01   02Dec18   Change size of LOB_REF
         DR66803-CKL-01   03Feb04   Define default interim field size for aggr
                                    UDFs
         DR66803-rgs-01  03Feb19    Redefine time/timestamp with zone.
      DR85421-kevinv-01  03Dec08    UDT support
         DR81673-CA3-01  03Sep02    Changes/Additions for V2R6.0
         DR86125-CKL-01  04Mar04    Fix FNC_free.
         DR96810-rgs-01  05Jul05    Adjust for 64 bit platforms.
      DR97161-rakesh-01  05Jul25    Porting of DR96810 to 6.0.2 branch.
         DR95355-th6-01  05Nov16    Support dynamic output parameters 
                                    for table function
         DR95403-fsk-01  05Oct24    LID
     DR88432-debbieg-01  06Feb15    Add Queryband FNC functions
        DR106050-fsk-01  06Jul20    BIGINT def
   DR106946-sb230132-01  06Oct18    Period dada type support.

        DR111840-fsk-01  07Mar13    Change BIGINT def to #define for older compilers
        DR114685-CKL-01  07Jun25    Enclose all functions within the extern 
                                    "C" statement
    DR114379-phanibr-01  07Nov15    Added FNC_GetStructuredAttributeCount and
                                    FNC_GetStructuredAttributeInfo
**********************************************************************/

/*******************************************************************/
/* NOTE: In order to use this file the user has to define SQL_TEXT */
/* prior to the include for this file in their source              */
/* code. SQL_TEXT needs to be defined to be the character set type */
/* used when the function was compiled. Example:                   */
/*                                                                 */
/* #define SQL_TEXT Latin_Text                                     */
/*                                                                 */
/* #include <sqltypes_td.h>                                        */
/*                                                                 */
/* SQL_TEXT can be:                                                */
/*                                                                 */
/* Unicode_Text, Latin_Text, Kanjisjis_Text, Kanji1_Text           */
/*                                                                 */
/*******************************************************************/
#ifdef __cplusplus
extern "C" {
#endif

#include <limits.h>
#include <stdlib.h>

#if ((INT_MAX < 2147483647) || (INT_MAX > 2147483647))
#error "A 'int' must be defined as 32 bits"
#endif

#define FNC_MAXNAMELEN 30
#define DEFINTERIMSIZE 64
#define PDT_DT 35                    /* DR106946-sb230132-01 */
#define FNC_MAXQUERYBANDSIZE   4106 /* Max QueryBand size in bytes */
#define FNC_MAXQUERYBANDSIZE_U 8212 /* Max Unicode Queryband size in bytes */

typedef unsigned short Unicode_Text;
typedef unsigned char Latin_Text;
typedef unsigned char Kanjisjis_Text;
typedef unsigned char Kanji1_Text;

typedef unsigned char CHARACTER;
typedef unsigned char BYTE;
typedef unsigned short GRAPHIC;

typedef signed char BYTEINT;
typedef short SMALLINT;
typedef int INTEGER;
typedef  long long   BIGINT;                   /* DR114379-phanibr-01 */

typedef double REAL;
typedef double DOUBLE_PRECISION;
typedef double FLOAT;



/* Database DECIMAL data types */
/* of the form DECIMAL(n,m) or  */
/* NUMERIC(n,m) */
typedef signed char DECIMAL1;   /* 1 <= n <= 2 */
typedef short DECIMAL2;  /* 2 <= n <= 4 */
typedef int DECIMAL4;   /* 4 <= n <= 9 */


typedef signed char NUMERIC1;   /* 1 <= n <= 2 */
typedef short NUMERIC2;  /* 2 <= n <= 4 */
typedef int NUMERIC4;   /* 4 <= n <= 9 */

typedef struct 
{
    unsigned int  low;
    int           high;
} DECIMAL8, NUMERIC8;       /*10 <= n <= 18 */

typedef struct 
{
    unsigned  int      int1;
    unsigned  int      int2;
    unsigned  int      int3;
    int                int4;
} DECIMAL16, NUMERIC16;       /*19 <= n <= 38 */

/* database CHARACTER types */

typedef Latin_Text CHARACTER_LATIN;
typedef Kanjisjis_Text CHARACTER_KANJISJIS;
typedef Kanji1_Text CHARACTER_KANJI1;
typedef Unicode_Text CHARACTER_UNICODE;

/* database VARCHAR type */

typedef Latin_Text VARCHAR_LATIN;
typedef Kanjisjis_Text VARCHAR_KANJISJIS;
typedef Kanji1_Text VARCHAR_KANJI1;
typedef Unicode_Text VARCHAR_UNICODE;
 
/* database VARBYTE type */

  /* Use this for reference to an existing varbyte */

typedef struct VARBYTE 
{
	int    length;		/* length of string */
	BYTE   bytes[1];		/* bytes - size must be adjusted */
} VARBYTE;

   /* Use this macro to define your own varbyte of specific length */
   /* like this:                                                   */
   /*                                                              */
   /* VARBYTE_M(30) myvbstr;                                       */

#define VARBYTE_M(len) struct { int length; BYTE bytes[len]; }

/* database VARGRAPHIC type */

/* use this for reference to an existing vargraphic */

typedef struct VARGRAPHIC {
	int      length;        /* length of string */
	GRAPHIC  graphic[1];	/* string - size must be adjusted */
} VARGRAPHIC;

   /* Use this macro to define your own vargraphic of specific length */
   /* like this:                                                      */
   /*                                                                 */
   /* VARGRAPHIC_M(30) myvgstr;                                       */

#define VARGRAPHIC_M(len) struct { int length; GRAPHIC graphic[len]; }

/* Type definitions for large objects */

typedef int  LOB_LOCATOR;
typedef int  LOB_RESULT_LOCATOR;
typedef int  LOB_CONTEXT_ID;
typedef unsigned long FNC_LobLength_t;

typedef struct LOB_REF
{
    unsigned char data[64];
} LOB_REF;

/* Type definitions for UDTs */

typedef int  UDT_HANDLE;

typedef int  PDT_HANDLE;                           /* DR106946-sb230132-01 */

/* DBS Information Structure */

typedef struct dbs_info_t 
{	
    SQL_TEXT  	UserAccount[FNC_MAXNAMELEN]; /* users account string */
	SQL_TEXT  	UserName[FNC_MAXNAMELEN];	    /* User name */
	int     UserId;		        /* User ID */
    short   StatementNo;        /* Current statement number for request */
    short   Host;               /* Host ID */
	int 	SessionNo;		    /* Session Number */
    int     RequestNo;          /* Current request number */
} dbs_info_t;

/* calls functions can make */

extern void FNC_DbsInfo(const dbs_info_t *);

extern void *FNC_DefMem(int len);

extern void *FNC_malloc(size_t size);

extern void FNC_free(void *ptr);

#define malloc FNC_malloc
#define free   FNC_free


extern void FNC_Trace_String(void *TraceStr);

extern void FNC_Trace_Write(int argc, void *argv[]);

extern void FNC_Trace_Write_DL(int argc, void *argv[], int length[]);

/* Large object access functions */

FNC_LobLength_t
FNC_GetLobLength( LOB_LOCATOR object );

FNC_LobLength_t
FNC_LobOpen( LOB_LOCATOR     object,
             LOB_CONTEXT_ID* ctxid,
             FNC_LobLength_t start,
             FNC_LobLength_t maxlength );

int
FNC_LobRead( LOB_CONTEXT_ID   ctxid,
             BYTE*            buffer,
             FNC_LobLength_t  buffer_length,
             FNC_LobLength_t* actual_length );

void
FNC_LobClose( LOB_CONTEXT_ID  ctxid );

int 
FNC_LobAppend( LOB_RESULT_LOCATOR     object,
               BYTE*                  data,
               FNC_LobLength_t        data_length,
               FNC_LobLength_t*       actual_length );

void
FNC_LobLoc2Ref( LOB_LOCATOR     locator,
                LOB_REF*        ref );

LOB_LOCATOR
FNC_LobRef2Loc( const LOB_REF*  ref );

/* UDT access functions */
void
FNC_GetDistinctValue( UDT_HANDLE    udtHandle,
                      void*         returnValue,
                      int           bufSize,
                      int*          length );

void
FNC_SetDistinctValue( UDT_HANDLE    udtHandle,
                      void*         newValue,
                      int           length );

void
FNC_GetStructuredAttribute( UDT_HANDLE  udtHandle,
                            char*       attributePath,
                            void*       returnValue,
                            int         bufSize,
                            int*        nullIndicator,
                            int*        length );

void
FNC_SetStructuredAttribute( UDT_HANDLE  udtHandle,
                            char*       attributePath,
                            void*       newValue,
                            int         nullIndicator,
                            int         length );

void
FNC_GetDistinctInputLob( UDT_HANDLE     udtHandle,
                         LOB_LOCATOR*   object );

void
FNC_GetDistinctResultLob( UDT_HANDLE            udtHandle,
                          LOB_RESULT_LOCATOR*   object );

void
FNC_GetStructuredInputLobAttribute( UDT_HANDLE      udtHandle,
                                    char*           attributePath,
                                    int*            nullIndicator,
                                    LOB_LOCATOR*    object );

void
FNC_GetStructuredResultLobAttribute( UDT_HANDLE             udtHandle,
                                     char*                  attributePath,
                                     LOB_RESULT_LOCATOR*    object );

void
FNC_GetInternalValue( UDT_HANDLE    udtHandle,
                      void*         returnValue,
                      int           bufSize,
                      int*          length );

void
FNC_SetInternalValue( UDT_HANDLE    udtHandle,
                      void*         newValue,
                      int           length );

FNC_LobLength_t
FNC_StructInternalTypeAttrSize( UDT_HANDLE  udtHandle,
                                char*       attributePath );

void
FNC_StructInternalTypeAttrSerializeToLob( UDT_HANDLE         udtHandle,
                                          char*              attributePath,
                                          LOB_RESULT_LOCATOR object,
                                          FNC_LobLength_t    *bytesWritten );

void
FNC_StructInternalTypeAttrDeserializeFromLob( UDT_HANDLE      udtHandle,
                                              char*           attributePath,
                                              LOB_LOCATOR     object,
                                              LOB_CONTEXT_ID  ctxid,
                                              FNC_LobLength_t length,
                                              FNC_LobLength_t *bytesRead );

void
FNC_GetStructuredAttributeCount( UDT_HANDLE udtHandle,
                                 int        *Attribute_count);


/* Macros for C Data Type sizes used by the UDT access functions. */
#define SIZEOF_CHARACTER_LATIN(len) ( (len) * sizeof(CHARACTER_LATIN) )
#define SIZEOF_CHARACTER_LATIN_WITH_NULL(len) ( (len) * sizeof(CHARACTER_LATIN) + sizeof(CHARACTER_LATIN) )
#define SIZEOF_CHARACTER_KANJISJIS(len) ( (len) * sizeof(CHARACTER_KANJISJIS) )
#define SIZEOF_CHARACTER_KANJISJIS_WITH_NULL(len) ( (len) * sizeof(CHARACTER_KANJISJIS) + sizeof(CHARACTER_KANJISJIS) )
#define SIZEOF_CHARACTER_KANJI1(len) ( (len) * sizeof(CHARACTER_KANJI1) )
#define SIZEOF_CHARACTER_KANJI1_WITH_NULL(len) ( (len) * sizeof(CHARACTER_KANJI1) + sizeof(CHARACTER_KANJI1) )
#define SIZEOF_CHARACTER_UNICODE(len) ( (len) * sizeof(CHARACTER_UNICODE) )
#define SIZEOF_CHARACTER_UNICODE_WITH_NULL(len) ( (len) * sizeof(CHARACTER_UNICODE) + sizeof(CHARACTER_UNICODE) )
#define SIZEOF_VARCHAR_LATIN(len) ( (len) * sizeof(VARCHAR_LATIN) )
#define SIZEOF_VARCHAR_LATIN_WITH_NULL(len) ( (len) * sizeof(VARCHAR_LATIN) + sizeof(VARCHAR_LATIN) )
#define SIZEOF_VARCHAR_KANJISJIS(len) ( (len) * sizeof(VARCHAR_KANJISJIS) )
#define SIZEOF_VARCHAR_KANJISJIS_WITH_NULL(len) ( (len) * sizeof(VARCHAR_KANJISJIS) + sizeof(VARCHAR_KANJISJIS) )
#define SIZEOF_VARCHAR_KANJI1(len) ( (len) * sizeof(VARCHAR_KANJI1) )
#define SIZEOF_VARCHAR_KANJI1_WITH_NULL(len) ( (len) * sizeof(VARCHAR_KANJI1) + sizeof(VARCHAR_KANJI1) )
#define SIZEOF_VARCHAR_UNICODE(len) ( (len) * sizeof(VARCHAR_UNICODE) )
#define SIZEOF_VARCHAR_UNICODE_WITH_NULL(len) ( (len) * sizeof(VARCHAR_UNICODE) + sizeof(VARCHAR_UNICODE) )
#define SIZEOF_VARBYTE(len) ( sizeof(int) + (len) * sizeof(BYTE) )
#define SIZEOF_BYTE(len) ( (len) * sizeof(BYTE) )
#define SIZEOF_GRAPHIC(len) ( (len) * sizeof(GRAPHIC) )
#define SIZEOF_VARGRAPHIC(len) ( sizeof(int) + (len) * sizeof(GRAPHIC) )
#define SIZEOF_SMALLINT ( sizeof(SMALLINT) )
#define SIZEOF_INTEGER ( sizeof(INTEGER) )
#define SIZEOF_BIGINT ( sizeof(int) + sizeof(int) )
#define SIZEOF_REAL ( sizeof(REAL) )
#define SIZEOF_DOUBLE_PRECISION ( sizeof(DOUBLE_PRECISION) )
#define SIZEOF_FLOAT ( sizeof(FLOAT) )
#define SIZEOF_DECIMAL1 ( sizeof(DECIMAL1) )
#define SIZEOF_DECIMAL2 ( sizeof(DECIMAL2) )
#define SIZEOF_DECIMAL4 ( sizeof(DECIMAL4) )
#define SIZEOF_DECIMAL8 ( sizeof(unsigned int) + sizeof(int) )
#define SIZEOF_DECIMAL16 ( sizeof(unsigned int) + sizeof(int) + sizeof(int) + sizeof(int) )
#define SIZEOF_NUMERIC1 ( sizeof(NUMERIC1) )
#define SIZEOF_NUMERIC2 ( sizeof(NUMERIC2) )
#define SIZEOF_NUMERIC4 ( sizeof(NUMERIC4) )
#define SIZEOF_NUMERIC8 ( sizeof(unsigned int) + sizeof(int) )
#define SIZEOF_NUMERIC16 ( sizeof(unsigned int) + sizeof(int) + sizeof(int) + sizeof(int) )
#define SIZEOF_BYTEINT ( sizeof(BYTEINT) )
#define SIZEOF_DATE ( sizeof(DATE) )
#define SIZEOF_ANSI_Time ( sizeof(DECIMAL4) + 2 * sizeof(BYTEINT) )
#define SIZEOF_TimeStamp ( sizeof(DECIMAL4) + sizeof(SMALLINT) + 4 * sizeof(BYTEINT) )
#define SIZEOF_INTERVAL_YEAR ( sizeof(INTERVAL_YEAR) )
#define SIZEOF_IntrvlYtoM ( 2 * sizeof(SMALLINT) )
#define SIZEOF_INTERVAL_MONTH ( sizeof(INTERVAL_MONTH) )
#define SIZEOF_INTERVAL_DAY ( sizeof(INTERVAL_DAY) )
#define SIZEOF_IntrvlDtoH ( 2 * sizeof(SMALLINT) )
#define SIZEOF_IntrvlDtoM ( 3 * sizeof(SMALLINT) + sizeof(short) )
#define SIZEOF_IntrvlDtoS ( sizeof(DECIMAL4) + 3 * sizeof(SMALLINT) )
#define SIZEOF_HOUR ( sizeof(HOUR) )
#define SIZEOF_IntrvlHtoM ( 2 * sizeof(SMALLINT) )
#define SIZEOF_IntrvlHtoS ( 2 * sizeof(SMALLINT) + sizeof(DECIMAL4) )
#define SIZEOF_MINUTE ( sizeof(MINUTE) )
#define SIZEOF_IntrvlMtoS ( sizeof(DECIMAL4) + sizeof(SMALLINT) )
#define SIZEOF_IntrvlSec ( sizeof(DECIMAL4) + sizeof(SMALLINT) )
#define SIZEOF_ANSI_Time_WZone ( sizeof(DECIMAL4) + 4 * sizeof(BYTEINT) )
#define SIZEOF_ANSI_TimeStamp_WZone ( sizeof(DECIMAL4) + sizeof(SMALLINT) + 6 * sizeof(BYTEINT) )

/****************************************************************/
/* Aggregate function phase enumeration type and table function */
/* phase enumeration                                            */
/****************************************************************/

typedef enum FNC_Phase_et {AGR_INIT=1, 
                           AGR_DETAIL=2, 
                           AGR_COMBINE=3, 
                           AGR_FINAL=4, 
                           AGR_NODATA=5, 
                           TBL_PRE_INIT = 20,
                           TBL_INIT = 21,
                           TBL_BUILD = 22,
                           TBL_FINI = 23,
                           TBL_END = 24,
                           TBL_ABORT = 25  
                       } FNC_Phase_et;

#define FNC_Phase BYTE


/* Purpose: to define the mode of the arguments to a table function.  */
typedef enum FNC_Mode_et
{
    TBL_MODE_VARY = 1,                             /* arguments vary */
    TBL_MODE_CONST = 2,                    /* arguments are constant */
} FNC_Mode_et;

#define FNC_Mode BYTE 

/* Purpose: to provide a structure for the amp-node pair */
typedef struct AMP_Node_t
{
    unsigned short NodeId;
    unsigned short AMPId;
} AMP_Node_t;

/* Purpose: to provide a structure that lists on-line amps  */
typedef struct FNC_Node_Info_t
{
    int NumAMPNodes;
    int NumAMPs;
    AMP_Node_t AN[1]; /* number varies with number of */
                       /* AMP vprocs (one per AMP vproc) */
} FNC_Node_Info_t;

/* Purpose: to provide structure for amp specific information */
typedef struct AMP_Info_t
{
    unsigned short NodeId;
    unsigned short AMPId;
    unsigned short LowestAMPOnNode;
} AMP_Info_t;

extern FNC_Mode FNC_GetPhase(FNC_Phase* Phase); 
extern int FNC_TblControl(void);
extern void *FNC_TblAllocCtrlCtx(int length);
extern void *FNC_TblGetCtrlCtx(void);
extern void *FNC_TblAllocCtx(int length);
extern void *FNC_TblGetCtx(void);
extern int FNC_TblOptOut(void);
extern int FNC_TblAbort(void);
extern FNC_Node_Info_t *FNC_TblGetNodeData(void);
extern AMP_Info_t *FNC_AMPInfo(void);
extern int FNC_TblFirstParticipant(void);

/*************/
/* DATE type */
/*************/

/* To be specific, the date has the following format: */
/*  ((year - 1900) * 10000 + (month * 100) + day)(INTEGER) */

typedef int DATE; 

/*************/
/* ANSI TIME */
/*************/

typedef struct ANSI_Time 
{
    DECIMAL4 seconds; /* represented as DECIMAL(8,6) */
    BYTEINT  hour;
    BYTEINT  minute;
} ANSI_Time;

/***********************/
/* ANSI TIMESTAMP type */
/***********************/

typedef struct TimeStamp 
{
    DECIMAL4 seconds;   /* represented as DECIMAL(8,6) */
    SMALLINT year;
    BYTEINT  month;
    BYTEINT  day;
    BYTEINT  hour;
    BYTEINT  minute;
} TimeStamp;

/*****************/
/* INTERVAL YEAR */
/*****************/

typedef SMALLINT INTERVAL_YEAR;

/**************************/
/* INTERVAL YEAR TO MONTH */
/**************************/

typedef struct IntrvlYtoM 
{
    SMALLINT year;
    SMALLINT month;
} IntrvlYtoM;

/******************/
/* INTERVAL MONTH */
/******************/

typedef SMALLINT INTERVAL_MONTH; 

/****************/
/* INTERVAL DAY */
/****************/

typedef SMALLINT INTERVAL_DAY;

/************************/
/* INTERVAL DAY TO HOUR */
/************************/

typedef struct IntrvlDtoH 
{
    SMALLINT day;
    SMALLINT hour;
} IntrvlDtoH;

/**************************/
/* INTERVAL DAY TO MINUTE */
/**************************/

typedef struct IntrvlDtoM 
{
    SMALLINT day;
    SMALLINT hour;
    SMALLINT minute;
    short pad;   /* contains no useful information */
} IntrvlDtoM;

/**************************/
/* INTERVAL DAY TO SECOND */
/**************************/

typedef struct IntrvlDtoS 
{
    DECIMAL4 seconds;  /* represented as a DECIMAL(8,6) */
    SMALLINT day;
    SMALLINT hour;
    SMALLINT minute;
} IntrvlDtoS;

/*****************/
/* INTERVAL HOUR */
/*****************/

typedef SMALLINT HOUR;

/***************************/
/* INTERVAL HOUR TO MINUTE */
/***************************/

typedef struct IntrvlHtoM 
{
    SMALLINT hour;
    SMALLINT minute;
} IntrvlHtoM;

/***************************/
/* INTERVAL HOUR TO SECOND */
/***************************/

typedef struct IntrvlHtoS 
{
    SMALLINT hour;
    SMALLINT minute;
    DECIMAL4 seconds; /* represented as a DECIMAL(8,6) */
} IntrvlHtoS;

/*******************/
/* INTERVAL MINUTE */
/*******************/

typedef SMALLINT MINUTE;

/*****************************/
/* INTERVAL MINUTE TO SECOND */
/*****************************/

typedef struct IntrvlMtoS 
{
    DECIMAL4 seconds; /* represented as a DECIMAL(8,6) */
    SMALLINT minute;
} IntrvlMtoS;

/*******************/
/* INTERVAL SECOND */
/*******************/

/* Note: fract_sec only contains the fractional seconds. The */
/* whole_sec contains the number of whole seconds            */

typedef struct IntrvlSec 
{
    DECIMAL4  fract_sec; /* represented as a DECIMAL(8,6) */
    SMALLINT whole_sec;
} IntrvlSec;

/***********************/
/* TIME WITH TIME ZONE */
/***********************/

typedef struct ANSI_Time_WZone 
{
    DECIMAL4 seconds; /* represented as DECIMAL(8,6) */
    BYTEINT  hour;
    BYTEINT  minute;
    BYTEINT  zone_hour;
    BYTEINT  zone_minutes;
} ANSI_Time_WZone;

/****************************/
/* TIMESTAMP WITH TIME ZONE */
/****************************/

typedef struct ANSI_TimeStamp_WZone 
{
    DECIMAL4 seconds;   /* represented as DECIMAL(8,6) */
    SMALLINT year;
    BYTEINT  month;
    BYTEINT  day;
    BYTEINT  hour;
    BYTEINT  minute;
    BYTEINT  zone_hour;
    BYTEINT  zone_minutes;
} ANSI_TimeStamp_WZone;


/**************************/
/* Function Context block */
/**************************/
/* Note: the function context block will have new fields added in */
/* future releases but existing fields will never be changed.     */

typedef struct
{
    unsigned unused   : 30;
    unsigned excl_row : 1;   /* bit 1: set exclude current row */ 
                             /* from OA window */
    unsigned last_row : 1;   /* bit 0: set means last row for OA group */
} FNC_flags_t;

typedef struct FNC_Context_t 
{
    int   version;        /* the version of this context */
    FNC_flags_t flags;    /* misc flags */
    void  *interim1;      /* pointer to intermediate storage 1 */
    int   intrm1_length;  /* length of interim1 area */
    void  *interim2;      /* pointer to intermediate storage 2 */
    int   intrm2_length;  /* length of interim2 area */
    long  group_count;    /* number of rows in statistical group */
    long  window_size;    /* the size of the statistical window */
    long  pre_window;     /* number of pre window rows */
    long  post_window;    /* number of post window rows */
} FNC_Context_t;

/*******************************************************/
/* Valid data type enumeration for FNC_CallSP support. */
/*******************************************************/

typedef enum dtype_en
{
        UNDEF_DT=0,   
        CHAR_DT=1,
        VARCHAR_DT=2,
        BYTE_DT=3,
        VARBYTE_DT=4,
        GRAPHIC_DT=5,
        VARGRAPHIC_DT=6,
        BYTEINT_DT=7,
        SMALLINT_DT=8,
        INTEGER_DT=9,
        BIGINT_DT=36,
        REAL_DT=10,
        DECIMAL1_DT=11,
        DECIMAL2_DT=12,
        DECIMAL4_DT=13,
        DECIMAL8_DT=14,
        DECIMAL16_DT=37,
        DATE_DT=15,
        TIME_DT=16,
        TIMESTAMP_DT=17,
        INTERVAL_YEAR_DT=18,
        INTERVAL_YTM_DT=19,
        INTERVAL_MONTH_DT=20,
        INTERVAL_DAY_DT=21,
        INTERVAL_DTH_DT=22,
        INTERVAL_DTM_DT=23,
        INTERVAL_DTS_DT=24,
        INTERVAL_HOUR_DT=25,
        INTERVAL_HTM_DT=26,
        INTERVAL_HTS_DT=27,
        INTERVAL_MINUTE_DT=28,
        INTERVAL_MTS_DT=29,
        INTERVAL_SECOND_DT=30,
        TIME_WTZ_DT=31,
        TIMESTAMP_WTZ_DT=32,
        BLOB_REFERENCE_DT=33,
        CLOB_REFERENCE_DT=34,
        UDT_DT=35
        /* The 8 byte integer type (BIGINT_DT) and
         * the 16 byte decimal type (DECIMAL16_DT) 
         * are located above and have the following
         * values:
         *
         * BIGINT_DT=36    
         * DECIMAL16_DT=37 
         */
} dtype_en;

typedef int dtype_et;

/* Valid Parameter modes */
typedef enum dmode_en
{
        UNDEF_PM=0,
        IN_PM=1,
        INOUT_PM=2,
        OUT_PM=3
} dmode_en;

typedef int dmode_et;

/* Valid character set types */

typedef enum charset_en
{
        UNDEF_CT=0,
        LATIN_CT=1,
        UNICODE_CT=2,
        KANJISJIS_CT=3,
        KANJI1_CT=4
} charset_en;

typedef int charset_et;

/*
** Structure that defines the parameters to the SP
** that is being called via a 'FNC_CallSP' call.
*/
typedef struct parm_t
{
        dtype_et      datatype;
        dmode_et      direction;
        charset_et    charset;

        union {

          int    length;        /* Length of CHAR/VARCHAR/BYTE/GRAPHIC dtypes */

          int    intervalrange; /* range for interval dtypes,
                                 * say, INTERVAL YEAR(4)
                                 */
          int    precision;     /* precision for time/timestamp dtypes,
                                 * say TIME(4) or TIMESTAMP(6) etc.
                                 */
          struct {
            int    totaldigit;  /* value 'm' in a DECIMAL(m, n) data-type */
            int    fracdigit;   /* value 'n' in a DECIMAL(m, n) data-type */
          } range;
        } size;
} parm_t;

/*
Notes on usage of parm_t:

  datatype      Data-type of the parameter.
  direction     IN/OUT/INOUT parameter?
  charset       Character set of the CHAR/VARCHAR data.
  size          Its a union of length, precision and range fields.

                LENGTH:
                -------

                  The length field must be filled out by the C-caller for BYTE,
                  GRAPHIC, CHAR and VARCHAR data-types.

                  ** For other data-types, the length field is not relevant. **

                * For CHAR_DT the length will be taken to be the defined
                  character length of the string i.e. the length mentioned 
                  in the parm_t (for Unicode the number of bytes will actually 
                  be twice the number characters). If the actual length of the 
                  CHAR string is shorter, appropriate padding would be 
                  internally added to the string.

                  The length passed to the SP/XSP being invoked inside 
                  FNC_CallSP will always be the length specified in the 
                  length field. If the actual length of the CHAR string 
                  is shorter, appropriate padding would be internally added 
                  to the string.

                * For VARCHAR_DT the length is based the string length, but not
                  to exceeding the number of characters specified in the length
                  field. The length passed to the SP/XSP being invoked inside 
                  FNC_CallSP would be the specified length or less if the 
                  string being passed is less.

                * For BYTE_DT the length will be as specified in the length
                  field.

                * For GRAPHIC_DT the length will be as specified in the length
                  field. Note a graphic is a two byte character.

                !!! NOTE !!!
                ------------
                  The LENGTH mentioned in parm_t should not be less than
                  one byte and greater than 64000 bytes. If the C string
                  is longer than the length specified in parm_t, then the
                  rest will be thrown away with no error. It is for the
                  C developer to do the proper checking.

                INTERVALRANGE:
                --------------
                * Specifies the range/precision for interval data-types.

                PRECISION:
                ----------
                * Specifies the precision for time/timestamp data-types.

                RANGE: (totaldigit, fracdigit)
                ------
                * Specifies the total-digit and fractional-digits value for
                  DECIMAL data-type of the form DECIMAL(m, n).

                !!! NOTE !!!
                ------------
                  INTERVAL SECOND should also use RANGE to represent
                  INTERVAL SECOND(m, n) form.
*/

/************************/
/* FNC_CallSP prototype */
/************************/

extern void
FNC_CallSP( SQL_TEXT     *SP_Name,
            int           argc,
            void         *argv[],
            int           ind[],
            parm_t        dtype[],
            char         *sqlstate );
      
/***********************************************/
/* QueryBand FNC prototypes                    */
/***********************************************/      

typedef struct 
{	
    void  	*QBName;  /* queryband name */
	void  	*QBValue; /* queryband value */
} FNC_QB_Pair_t;

/* Purpose: to specify types of queryband searches */
typedef enum
{
    QB_FIRST = 0,   
    QB_TXN = 1,     
    QB_SESSION = 2 
} FNC_QBSearch_et;

extern void
FNC_GetQueryBand( void*      QBandBuf,
                  int        BufSize,
                  int*       QBandLen);
                  
extern FNC_QB_Pair_t *
FNC_GetQueryBandPairs( 
            void            *QBandBuf,
            FNC_QBSearch_et  QB_SearchType,
            int             *NumPairs);
                       
extern void
FNC_GetQueryBandValue( 
            void            *QBandBuf,
            FNC_QBSearch_et  QB_SearchType,
            void            *QBName,
            void            *QBValue);


/* Purpose to provide structure for table function runtime */
/* column definition                                       */

typedef struct FNC_ColumnDef_t
{
   int      num_columns;
   parm_t   column_types[1];        
} FNC_ColumnDef_t; 

/*  num_columns          
        maximum number of output parameters
    column_types 
        column data type information 

*/
extern FNC_ColumnDef_t *FNC_TblGetColDef(void); 

typedef struct attribute_info_t
{
    INTEGER     attrIndex;                 /* Attribute positional index */
    dtype_en    data_type;           /* attribute data type */
    CHARACTER   attribute_name[256]; /* up to 256 byte attribute name */
    SMALLINT    udt_indicator;       /* 0==None;1==Struct;2==Distinct;3==Internal*/
    CHARACTER   udt_type_name[256];  /* up to 256 byte UDT type name */
    INTEGER     max_length;          /* Max length for this data type */
    BIGINT      lob_length;          /* LOB length for LOB data types */
    SMALLINT    total_interval_digits;    /* see usage notes below */
    SMALLINT    num_fractional_digits;    /* see usage notes below */
    charset_en  charset_code;             /* Character Set */
} attribute_info_t;

void  FNC_GetStructuredAttributeInfo( UDT_HANDLE AnyStructuredUdt,
                                      int        attribute_position,
                                      int        bufSize,
                                      attribute_info_t  * attributeArray );
#ifdef __cplusplus
}
#endif

#endif 
```
