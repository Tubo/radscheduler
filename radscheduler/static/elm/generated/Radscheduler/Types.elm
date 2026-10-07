module Radscheduler.Types exposing
    ( ErrorOut, FullCalendarHolidaySchema, FullCalendarLeaveSchema, FullCalendarShiftSchema, HolidayOut, LeaveOut
    , LeavePatch, PreviewOut, PublishedRange, RegistrarOut, RosterOut, ShiftIn
    , ShiftOut, ShiftPatch
    , LeaveType(..), ShiftType(..), leaveTypeFromString, leaveTypeToString, leaveTypeVariants, shiftTypeFromString
    , shiftTypeToString, shiftTypeVariants
    )

{-|


## Aliases

@docs ErrorOut, FullCalendarHolidaySchema, FullCalendarLeaveSchema, FullCalendarShiftSchema, HolidayOut, LeaveOut
@docs LeavePatch, PreviewOut, PublishedRange, RegistrarOut, RosterOut, ShiftIn
@docs ShiftOut, ShiftPatch


## Enum

@docs LeaveType, ShiftType, leaveTypeFromString, leaveTypeToString, leaveTypeVariants, shiftTypeFromString
@docs shiftTypeToString, shiftTypeVariants

-}

import Date
import OpenApi.Common
import Time


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


type alias HolidayOut =
    { date : Date.Date, name : String }


type alias LeaveOut =
    { cancelled : Bool
    , comment : String
    , created : Time.Posix
    , date : Date.Date
    , dot_approved : OpenApi.Common.Nullable Bool
    , id : Int
    , last_edited : Time.Posix
    , portion : String
    , reg_approved : OpenApi.Common.Nullable Bool
    , registrar : Int
    , type_ : LeaveType
    }


type alias LeavePatch =
    { cancelled : Maybe Bool
    , dot_approved : Maybe (OpenApi.Common.Nullable Bool)
    , reg_approved : Maybe (OpenApi.Common.Nullable Bool)
    }


type alias PreviewOut =
    { leave_hidden : Int
    , leave_shown : Int
    , shifts_hidden : Int
    , shifts_shown : Int
    }


type alias PublishedRange =
    { end : Date.Date, start : Date.Date }


type alias RegistrarOut =
    { id : Int, username : String, year : OpenApi.Common.Nullable Int }


type alias RosterOut =
    { dates : List Date.Date
    , holidays : List HolidayOut
    , leaves : List LeaveOut
    , next : Date.Date
    , prev : Date.Date
    , published : OpenApi.Common.Nullable PublishedRange
    , registrars : List RegistrarOut
    , shifts : List ShiftOut
    , today : Date.Date
    , week : Date.Date
    }


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
