module Radscheduler.Types exposing
    ( AwayOut, ChecksOut, ErrorOut, FullCalendarHolidaySchema, FullCalendarLeaveSchema, FullCalendarShiftSchema
    , GapOut, HolidayOut, LeaveOut, LeaveOverviewOut, LeavePatch, LeaveRequestOut
    , LeaveRequestsOut, LeaveTallyOut, LeaveYearOut, LeavesPatch, PreviewOut, PublishedRange
    , RegistrarOut, RequestChecksOut, RequestDayOut, RequestRowOut, RosterOut, ShiftCountsOut
    , ShiftIn, ShiftOut, ShiftPatch, ShiftPeriodOut, ShiftTallyOut, StatusOut
    , ViolationOut, WaitingCountsOut, WorkloadOut
    , LeaveType(..), ShiftType(..), StatusType(..), leaveTypeFromString, leaveTypeToString, leaveTypeVariants
    , shiftTypeFromString, shiftTypeToString, shiftTypeVariants, statusTypeFromString, statusTypeToString, statusTypeVariants
    )

{-|


## Aliases

@docs AwayOut, ChecksOut, ErrorOut, FullCalendarHolidaySchema, FullCalendarLeaveSchema, FullCalendarShiftSchema
@docs GapOut, HolidayOut, LeaveOut, LeaveOverviewOut, LeavePatch, LeaveRequestOut
@docs LeaveRequestsOut, LeaveTallyOut, LeaveYearOut, LeavesPatch, PreviewOut, PublishedRange
@docs RegistrarOut, RequestChecksOut, RequestDayOut, RequestRowOut, RosterOut, ShiftCountsOut
@docs ShiftIn, ShiftOut, ShiftPatch, ShiftPeriodOut, ShiftTallyOut, StatusOut
@docs ViolationOut, WaitingCountsOut, WorkloadOut


## Enum

@docs LeaveType, ShiftType, StatusType, leaveTypeFromString, leaveTypeToString, leaveTypeVariants
@docs shiftTypeFromString, shiftTypeToString, shiftTypeVariants, statusTypeFromString, statusTypeToString, statusTypeVariants

-}

import Date
import OpenApi.Common
import Time


{-| Someone else's leave on a day next to a request: approved, or still waiting for a decision.
-}
type alias AwayOut =
    { approved : Bool
    , date : Date.Date
    , portion : String
    , registrar : Int
    , type_ : LeaveType
    }


type alias ChecksOut =
    { variances : List ViolationOut
    , violations : List ViolationOut
    , workload : List WorkloadOut
    }


type alias ErrorOut =
    { detail : String }


type alias FullCalendarHolidaySchema =
    { allDay : Maybe Bool
    , event_type : Maybe String
    , id : Maybe Int
    , start : Date.Date
    , title : String
    }


type alias FullCalendarLeaveSchema =
    { allDay : Maybe Bool
    , event_type : Maybe String
    , id : Maybe (OpenApi.Common.Nullable Int)
    , start : Date.Date
    , title : String
    }


type alias FullCalendarShiftSchema =
    { allDay : Maybe Bool
    , event_type : Maybe String
    , id : Maybe (OpenApi.Common.Nullable Int)
    , start : Date.Date
    , title : String
    }


type alias GapOut =
    { date : Date.Date, needs : List (List ShiftType) }


type alias HolidayOut =
    { date : Date.Date, name : String }


type alias LeaveOut =
    { cancelled : Bool
    , comment : String
    , created : Time.Posix
    , date : Date.Date
    , dot_approved : OpenApi.Common.Nullable Bool
    , dot_decided_at : OpenApi.Common.Nullable Time.Posix
    , dot_decided_by : OpenApi.Common.Nullable String
    , id : Int
    , last_edited : Time.Posix
    , microster : Bool
    , portion : String
    , printed : Bool
    , reg_approved : OpenApi.Common.Nullable Bool
    , reg_decided_at : OpenApi.Common.Nullable Time.Posix
    , reg_decided_by : OpenApi.Common.Nullable String
    , registrar : Int
    , type_ : LeaveType
    }


type alias LeaveOverviewOut =
    { registrars : List RegistrarOut, rows : List RequestRowOut, total : Int }


type alias LeavePatch =
    { cancelled : Maybe Bool
    , dot_approved : Maybe (OpenApi.Common.Nullable Bool)
    , microster : Maybe Bool
    , reg_approved : Maybe (OpenApi.Common.Nullable Bool)
    }


type alias LeaveRequestOut =
    { asked : OpenApi.Common.Nullable Time.Posix
    , away : List AwayOut
    , dates : List Date.Date
    , days : List RequestDayOut
    , existing_violations : List ViolationOut
    , leaves : List LeaveOut
    , other_leave : List LeaveOut
    , registrar : Int
    , shifts : List ShiftOut
    , violations : List ViolationOut
    , years : List LeaveYearOut
    }


type alias LeaveRequestsOut =
    { holidays : List HolidayOut
    , registrars : List RegistrarOut
    , requests : List LeaveRequestOut
    , total : Int
    }


type alias LeaveTallyOut =
    { approved : Float, request : Float, type_ : LeaveType, waiting : Float }


type alias LeaveYearOut =
    { end : Date.Date
    , lead : Bool
    , start : Date.Date
    , types : List LeaveTallyOut
    }


{-| The same change to several days of leave, e.g. approving a whole request.
-}
type alias LeavesPatch =
    { cancelled : Maybe Bool
    , dot_approved : Maybe (OpenApi.Common.Nullable Bool)
    , ids : List Int
    , microster : Maybe Bool
    , reg_approved : Maybe (OpenApi.Common.Nullable Bool)
    }


type alias PreviewOut =
    { checked_to : OpenApi.Common.Nullable Date.Date
    , gaps : List GapOut
    , leave_hidden : Int
    , leave_shown : Int
    , leave_waiting : Int
    , shifts_hidden : Int
    , shifts_shown : Int
    , violations : List ViolationOut
    }


type alias PublishedRange =
    { end : Date.Date, start : Date.Date }


type alias RegistrarOut =
    { id : Int
    , name : String
    , username : String
    , year : OpenApi.Common.Nullable Int
    }


{-| What a waiting request's verdict turns on.
-}
type alias RequestChecksOut =
    { away : Float
    , breaks : Int
    , days : Int
    , lost : Int
    , roster : Int
    , unrostered : Int
    }


type alias RequestDayOut =
    { date : Date.Date
    , lost : List (List ShiftType)
    , registrars : Int
    , rostered : Bool
    , short : List (List ShiftType)
    }


{-| A request in the overview, keyed by its first day's id.
-}
type alias RequestRowOut =
    { asked : OpenApi.Common.Nullable Time.Posix
    , checks : OpenApi.Common.Nullable RequestChecksOut
    , comment : String
    , days : Float
    , decided : OpenApi.Common.Nullable Time.Posix
    , end : Date.Date
    , key : Int
    , leaves : List LeaveOut
    , portion : String
    , registrar : Int
    , start : Date.Date
    , status : String
    , type_ : LeaveType
    }


type alias RosterOut =
    { checks : ChecksOut
    , dates : List Date.Date
    , holidays : List HolidayOut
    , leaves : List LeaveOut
    , next : Date.Date
    , prev : Date.Date
    , published : OpenApi.Common.Nullable PublishedRange
    , registrars : List RegistrarOut
    , shifts : List ShiftOut
    , statuses : List StatusOut
    , today : Date.Date
    , week : Date.Date
    }


type alias ShiftCountsOut =
    { periods : List ShiftPeriodOut, registrar : Int }


type alias ShiftIn =
    { date : Date.Date
    , extra_duty : Maybe Bool
    , registrar : Int
    , type_ : ShiftType
    }


type alias ShiftOut =
    { date : Date.Date
    , extra_duty : Bool
    , id : Int
    , registrar : OpenApi.Common.Nullable Int
    , type_ : ShiftType
    }


type alias ShiftPatch =
    { extra_duty : Maybe Bool, type_ : Maybe ShiftType }


type alias ShiftPeriodOut =
    { end : Date.Date
    , name : String
    , peers : Int
    , shifts : List ShiftTallyOut
    , start : Date.Date
    }


type alias ShiftTallyOut =
    { count : Int
    , max : OpenApi.Common.Nullable Int
    , mean : OpenApi.Common.Nullable Float
    , median : OpenApi.Common.Nullable Float
    , min : OpenApi.Common.Nullable Int
    , type_ : ShiftType
    }


type alias StatusOut =
    { comment : String
    , end : Date.Date
    , id : Int
    , registrar : Int
    , shift_types : List ShiftType
    , start : Date.Date
    , type_ : StatusType
    , weekdays : List Int
    }


type alias ViolationOut =
    { clause : OpenApi.Common.Nullable String
    , dates : List Date.Date
    , message : String
    , registrar : Int
    , rule : String
    , variance : OpenApi.Common.Nullable String
    }


type alias WaitingCountsOut =
    { all : Int, mine : OpenApi.Common.Nullable Int }


type alias WorkloadOut =
    { load : Float, registrar : Int }


type LeaveType
    = LeaveType__ANNUAL
    | LeaveType__BE
    | LeaveType__CONF
    | LeaveType__EDU
    | LeaveType__LIEU
    | LeaveType__PAR
    | LeaveType__SICK


type ShiftType
    = ShiftType__HELP
    | ShiftType__LONG
    | ShiftType__NIGHT
    | ShiftType__RDO
    | ShiftType__SLEEP
    | ShiftType__SWING


type StatusType
    = StatusType__BUDDY
    | StatusType__NA
    | StatusType__PART
    | StatusType__PRECALL
    | StatusType__PREEXAM
    | StatusType__RELIEVER


leaveTypeFromString : String -> Maybe LeaveType
leaveTypeFromString value =
    case value of
        "ANNUAL" ->
            Just LeaveType__ANNUAL

        "BE" ->
            Just LeaveType__BE

        "CONF" ->
            Just LeaveType__CONF

        "EDU" ->
            Just LeaveType__EDU

        "LIEU" ->
            Just LeaveType__LIEU

        "PAR" ->
            Just LeaveType__PAR

        "SICK" ->
            Just LeaveType__SICK

        _ ->
            Nothing


leaveTypeToString : LeaveType -> String
leaveTypeToString value =
    case value of
        LeaveType__ANNUAL ->
            "ANNUAL"

        LeaveType__BE ->
            "BE"

        LeaveType__CONF ->
            "CONF"

        LeaveType__EDU ->
            "EDU"

        LeaveType__LIEU ->
            "LIEU"

        LeaveType__PAR ->
            "PAR"

        LeaveType__SICK ->
            "SICK"


leaveTypeVariants : List LeaveType
leaveTypeVariants =
    [ LeaveType__ANNUAL
    , LeaveType__BE
    , LeaveType__CONF
    , LeaveType__EDU
    , LeaveType__LIEU
    , LeaveType__PAR
    , LeaveType__SICK
    ]


shiftTypeFromString : String -> Maybe ShiftType
shiftTypeFromString value =
    case value of
        "HELP" ->
            Just ShiftType__HELP

        "LONG" ->
            Just ShiftType__LONG

        "NIGHT" ->
            Just ShiftType__NIGHT

        "RDO" ->
            Just ShiftType__RDO

        "SLEEP" ->
            Just ShiftType__SLEEP

        "SWING" ->
            Just ShiftType__SWING

        _ ->
            Nothing


shiftTypeToString : ShiftType -> String
shiftTypeToString value =
    case value of
        ShiftType__HELP ->
            "HELP"

        ShiftType__LONG ->
            "LONG"

        ShiftType__NIGHT ->
            "NIGHT"

        ShiftType__RDO ->
            "RDO"

        ShiftType__SLEEP ->
            "SLEEP"

        ShiftType__SWING ->
            "SWING"


shiftTypeVariants : List ShiftType
shiftTypeVariants =
    [ ShiftType__HELP
    , ShiftType__LONG
    , ShiftType__NIGHT
    , ShiftType__RDO
    , ShiftType__SLEEP
    , ShiftType__SWING
    ]


statusTypeFromString : String -> Maybe StatusType
statusTypeFromString value =
    case value of
        "BUDDY" ->
            Just StatusType__BUDDY

        "NA" ->
            Just StatusType__NA

        "PART" ->
            Just StatusType__PART

        "PRECALL" ->
            Just StatusType__PRECALL

        "PREEXAM" ->
            Just StatusType__PREEXAM

        "RELIEVER" ->
            Just StatusType__RELIEVER

        _ ->
            Nothing


statusTypeToString : StatusType -> String
statusTypeToString value =
    case value of
        StatusType__BUDDY ->
            "BUDDY"

        StatusType__NA ->
            "NA"

        StatusType__PART ->
            "PART"

        StatusType__PRECALL ->
            "PRECALL"

        StatusType__PREEXAM ->
            "PREEXAM"

        StatusType__RELIEVER ->
            "RELIEVER"


statusTypeVariants : List StatusType
statusTypeVariants =
    [ StatusType__BUDDY
    , StatusType__NA
    , StatusType__PART
    , StatusType__PRECALL
    , StatusType__PREEXAM
    , StatusType__RELIEVER
    ]
