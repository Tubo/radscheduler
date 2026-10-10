module Radscheduler.Json exposing
    ( encodeAwayOut, encodeChecksOut, encodeErrorOut, encodeFullCalendarHolidaySchema, encodeFullCalendarLeaveSchema, encodeFullCalendarShiftSchema
    , encodeGapOut, encodeHolidayOut, encodeLeaveOut, encodeLeaveOverviewOut, encodeLeavePatch, encodeLeaveRequestOut
    , encodeLeaveRequestsOut, encodeLeaveTallyOut, encodeLeaveType, encodeLeaveYearOut, encodeLeavesPatch, encodePreviewOut
    , encodePublishedRange, encodeRegistrarOut, encodeRequestChecksOut, encodeRequestDayOut, encodeRequestRowOut, encodeRosterOut
    , encodeShiftCountsOut, encodeShiftIn, encodeShiftOut, encodeShiftPatch, encodeShiftPeriodOut, encodeShiftTallyOut
    , encodeShiftType, encodeStatusOut, encodeStatusType, encodeViolationOut, encodeWaitingCountsOut, encodeWorkloadOut
    , decodeAwayOut, decodeChecksOut, decodeErrorOut, decodeFullCalendarHolidaySchema, decodeFullCalendarLeaveSchema, decodeFullCalendarShiftSchema
    , decodeGapOut, decodeHolidayOut, decodeLeaveOut, decodeLeaveOverviewOut, decodeLeavePatch, decodeLeaveRequestOut
    , decodeLeaveRequestsOut, decodeLeaveTallyOut, decodeLeaveType, decodeLeaveYearOut, decodeLeavesPatch, decodePreviewOut
    , decodePublishedRange, decodeRegistrarOut, decodeRequestChecksOut, decodeRequestDayOut, decodeRequestRowOut, decodeRosterOut
    , decodeShiftCountsOut, decodeShiftIn, decodeShiftOut, decodeShiftPatch, decodeShiftPeriodOut, decodeShiftTallyOut
    , decodeShiftType, decodeStatusOut, decodeStatusType, decodeViolationOut, decodeWaitingCountsOut, decodeWorkloadOut
    )

{-|


## Encoders

@docs encodeAwayOut, encodeChecksOut, encodeErrorOut, encodeFullCalendarHolidaySchema, encodeFullCalendarLeaveSchema, encodeFullCalendarShiftSchema
@docs encodeGapOut, encodeHolidayOut, encodeLeaveOut, encodeLeaveOverviewOut, encodeLeavePatch, encodeLeaveRequestOut
@docs encodeLeaveRequestsOut, encodeLeaveTallyOut, encodeLeaveType, encodeLeaveYearOut, encodeLeavesPatch, encodePreviewOut
@docs encodePublishedRange, encodeRegistrarOut, encodeRequestChecksOut, encodeRequestDayOut, encodeRequestRowOut, encodeRosterOut
@docs encodeShiftCountsOut, encodeShiftIn, encodeShiftOut, encodeShiftPatch, encodeShiftPeriodOut, encodeShiftTallyOut
@docs encodeShiftType, encodeStatusOut, encodeStatusType, encodeViolationOut, encodeWaitingCountsOut, encodeWorkloadOut


## Decoders

@docs decodeAwayOut, decodeChecksOut, decodeErrorOut, decodeFullCalendarHolidaySchema, decodeFullCalendarLeaveSchema, decodeFullCalendarShiftSchema
@docs decodeGapOut, decodeHolidayOut, decodeLeaveOut, decodeLeaveOverviewOut, decodeLeavePatch, decodeLeaveRequestOut
@docs decodeLeaveRequestsOut, decodeLeaveTallyOut, decodeLeaveType, decodeLeaveYearOut, decodeLeavesPatch, decodePreviewOut
@docs decodePublishedRange, decodeRegistrarOut, decodeRequestChecksOut, decodeRequestDayOut, decodeRequestRowOut, decodeRosterOut
@docs decodeShiftCountsOut, decodeShiftIn, decodeShiftOut, decodeShiftPatch, decodeShiftPeriodOut, decodeShiftTallyOut
@docs decodeShiftType, decodeStatusOut, decodeStatusType, decodeViolationOut, decodeWaitingCountsOut, decodeWorkloadOut

-}

import Date
import Json.Decode
import Json.Encode
import OpenApi.Common
import Radscheduler.Types
import Time


encodeAwayOut : Radscheduler.Types.AwayOut -> Json.Encode.Value
encodeAwayOut rec =
    Json.Encode.object
        [ ( "approved", Json.Encode.bool rec.approved )
        , ( "date", OpenApi.Common.encodeStringDate rec.date )
        , ( "portion", Json.Encode.string rec.portion )
        , ( "registrar", Json.Encode.int rec.registrar )
        , ( "type", encodeLeaveType rec.type_ )
        ]


encodeChecksOut : Radscheduler.Types.ChecksOut -> Json.Encode.Value
encodeChecksOut rec =
    Json.Encode.object
        [ ( "variances", Json.Encode.list encodeViolationOut rec.variances )
        , ( "violations", Json.Encode.list encodeViolationOut rec.violations )
        , ( "workload", Json.Encode.list encodeWorkloadOut rec.workload )
        ]


encodeErrorOut : Radscheduler.Types.ErrorOut -> Json.Encode.Value
encodeErrorOut rec =
    Json.Encode.object [ ( "detail", Json.Encode.string rec.detail ) ]


encodeFullCalendarHolidaySchema : Radscheduler.Types.FullCalendarHolidaySchema -> Json.Encode.Value
encodeFullCalendarHolidaySchema rec =
    Json.Encode.object
        (List.filterMap
            Basics.identity
            [ Maybe.map
                (\mapUnpack -> ( "allDay", Json.Encode.bool mapUnpack ))
                rec.allDay
            , Maybe.map
                (\mapUnpack -> ( "event_type", Json.Encode.string mapUnpack ))
                rec.event_type
            , Maybe.map
                (\mapUnpack -> ( "id", Json.Encode.int mapUnpack ))
                rec.id
            , Just ( "start", OpenApi.Common.encodeStringDate rec.start )
            , Just ( "title", Json.Encode.string rec.title )
            ]
        )


encodeFullCalendarLeaveSchema : Radscheduler.Types.FullCalendarLeaveSchema -> Json.Encode.Value
encodeFullCalendarLeaveSchema rec =
    Json.Encode.object
        (List.filterMap
            Basics.identity
            [ Maybe.map
                (\mapUnpack -> ( "allDay", Json.Encode.bool mapUnpack ))
                rec.allDay
            , Maybe.map
                (\mapUnpack -> ( "event_type", Json.Encode.string mapUnpack ))
                rec.event_type
            , Maybe.map
                (\mapUnpack ->
                    ( "id"
                    , case mapUnpack of
                        OpenApi.Common.Null ->
                            Json.Encode.null

                        OpenApi.Common.Present value ->
                            Json.Encode.int value
                    )
                )
                rec.id
            , Just ( "start", OpenApi.Common.encodeStringDate rec.start )
            , Just ( "title", Json.Encode.string rec.title )
            ]
        )


encodeFullCalendarShiftSchema : Radscheduler.Types.FullCalendarShiftSchema -> Json.Encode.Value
encodeFullCalendarShiftSchema rec =
    Json.Encode.object
        (List.filterMap
            Basics.identity
            [ Maybe.map
                (\mapUnpack -> ( "allDay", Json.Encode.bool mapUnpack ))
                rec.allDay
            , Maybe.map
                (\mapUnpack -> ( "event_type", Json.Encode.string mapUnpack ))
                rec.event_type
            , Maybe.map
                (\mapUnpack ->
                    ( "id"
                    , case mapUnpack of
                        OpenApi.Common.Null ->
                            Json.Encode.null

                        OpenApi.Common.Present value ->
                            Json.Encode.int value
                    )
                )
                rec.id
            , Just ( "start", OpenApi.Common.encodeStringDate rec.start )
            , Just ( "title", Json.Encode.string rec.title )
            ]
        )


encodeGapOut : Radscheduler.Types.GapOut -> Json.Encode.Value
encodeGapOut rec =
    Json.Encode.object
        [ ( "date", OpenApi.Common.encodeStringDate rec.date )
        , ( "needs"
          , Json.Encode.list (Json.Encode.list encodeShiftType) rec.needs
          )
        ]


encodeHolidayOut : Radscheduler.Types.HolidayOut -> Json.Encode.Value
encodeHolidayOut rec =
    Json.Encode.object
        [ ( "date", OpenApi.Common.encodeStringDate rec.date )
        , ( "name", Json.Encode.string rec.name )
        ]


encodeLeaveOut : Radscheduler.Types.LeaveOut -> Json.Encode.Value
encodeLeaveOut rec =
    Json.Encode.object
        [ ( "cancelled", Json.Encode.bool rec.cancelled )
        , ( "comment", Json.Encode.string rec.comment )
        , ( "created", OpenApi.Common.encodeStringDateTime rec.created )
        , ( "date", OpenApi.Common.encodeStringDate rec.date )
        , ( "dot_approved"
          , case rec.dot_approved of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    Json.Encode.bool value
          )
        , ( "dot_decided_at"
          , case rec.dot_decided_at of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    OpenApi.Common.encodeStringDateTime value
          )
        , ( "dot_decided_by"
          , case rec.dot_decided_by of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    Json.Encode.string value
          )
        , ( "id", Json.Encode.int rec.id )
        , ( "last_edited", OpenApi.Common.encodeStringDateTime rec.last_edited )
        , ( "microster", Json.Encode.bool rec.microster )
        , ( "portion", Json.Encode.string rec.portion )
        , ( "printed", Json.Encode.bool rec.printed )
        , ( "reg_approved"
          , case rec.reg_approved of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    Json.Encode.bool value
          )
        , ( "reg_decided_at"
          , case rec.reg_decided_at of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    OpenApi.Common.encodeStringDateTime value
          )
        , ( "reg_decided_by"
          , case rec.reg_decided_by of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    Json.Encode.string value
          )
        , ( "registrar", Json.Encode.int rec.registrar )
        , ( "type", encodeLeaveType rec.type_ )
        ]


encodeLeaveOverviewOut : Radscheduler.Types.LeaveOverviewOut -> Json.Encode.Value
encodeLeaveOverviewOut rec =
    Json.Encode.object
        [ ( "registrars", Json.Encode.list encodeRegistrarOut rec.registrars )
        , ( "rows", Json.Encode.list encodeRequestRowOut rec.rows )
        , ( "total", Json.Encode.int rec.total )
        ]


encodeLeavePatch : Radscheduler.Types.LeavePatch -> Json.Encode.Value
encodeLeavePatch rec =
    Json.Encode.object
        (List.filterMap
            Basics.identity
            [ Maybe.map
                (\mapUnpack -> ( "cancelled", Json.Encode.bool mapUnpack ))
                rec.cancelled
            , Maybe.map
                (\mapUnpack ->
                    ( "dot_approved"
                    , case mapUnpack of
                        OpenApi.Common.Null ->
                            Json.Encode.null

                        OpenApi.Common.Present value ->
                            Json.Encode.bool value
                    )
                )
                rec.dot_approved
            , Maybe.map
                (\mapUnpack -> ( "microster", Json.Encode.bool mapUnpack ))
                rec.microster
            , Maybe.map
                (\mapUnpack ->
                    ( "reg_approved"
                    , case mapUnpack of
                        OpenApi.Common.Null ->
                            Json.Encode.null

                        OpenApi.Common.Present value ->
                            Json.Encode.bool value
                    )
                )
                rec.reg_approved
            ]
        )


encodeLeaveRequestOut : Radscheduler.Types.LeaveRequestOut -> Json.Encode.Value
encodeLeaveRequestOut rec =
    Json.Encode.object
        [ ( "asked"
          , case rec.asked of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    OpenApi.Common.encodeStringDateTime value
          )
        , ( "away", Json.Encode.list encodeAwayOut rec.away )
        , ( "dates"
          , Json.Encode.list OpenApi.Common.encodeStringDate rec.dates
          )
        , ( "days", Json.Encode.list encodeRequestDayOut rec.days )
        , ( "existing_violations"
          , Json.Encode.list encodeViolationOut rec.existing_violations
          )
        , ( "leaves", Json.Encode.list encodeLeaveOut rec.leaves )
        , ( "other_leave", Json.Encode.list encodeLeaveOut rec.other_leave )
        , ( "registrar", Json.Encode.int rec.registrar )
        , ( "shifts", Json.Encode.list encodeShiftOut rec.shifts )
        , ( "violations", Json.Encode.list encodeViolationOut rec.violations )
        , ( "years", Json.Encode.list encodeLeaveYearOut rec.years )
        ]


encodeLeaveRequestsOut : Radscheduler.Types.LeaveRequestsOut -> Json.Encode.Value
encodeLeaveRequestsOut rec =
    Json.Encode.object
        [ ( "holidays", Json.Encode.list encodeHolidayOut rec.holidays )
        , ( "registrars", Json.Encode.list encodeRegistrarOut rec.registrars )
        , ( "requests", Json.Encode.list encodeLeaveRequestOut rec.requests )
        , ( "total", Json.Encode.int rec.total )
        ]


encodeLeaveTallyOut : Radscheduler.Types.LeaveTallyOut -> Json.Encode.Value
encodeLeaveTallyOut rec =
    Json.Encode.object
        [ ( "approved", Json.Encode.float rec.approved )
        , ( "request", Json.Encode.float rec.request )
        , ( "type", encodeLeaveType rec.type_ )
        , ( "waiting", Json.Encode.float rec.waiting )
        ]


encodeLeaveType : Radscheduler.Types.LeaveType -> Json.Encode.Value
encodeLeaveType rec =
    Json.Encode.string (Radscheduler.Types.leaveTypeToString rec)


encodeLeaveYearOut : Radscheduler.Types.LeaveYearOut -> Json.Encode.Value
encodeLeaveYearOut rec =
    Json.Encode.object
        [ ( "end", OpenApi.Common.encodeStringDate rec.end )
        , ( "lead", Json.Encode.bool rec.lead )
        , ( "start", OpenApi.Common.encodeStringDate rec.start )
        , ( "types", Json.Encode.list encodeLeaveTallyOut rec.types )
        ]


encodeLeavesPatch : Radscheduler.Types.LeavesPatch -> Json.Encode.Value
encodeLeavesPatch rec =
    Json.Encode.object
        (List.filterMap
            Basics.identity
            [ Maybe.map
                (\mapUnpack -> ( "cancelled", Json.Encode.bool mapUnpack ))
                rec.cancelled
            , Maybe.map
                (\mapUnpack ->
                    ( "dot_approved"
                    , case mapUnpack of
                        OpenApi.Common.Null ->
                            Json.Encode.null

                        OpenApi.Common.Present value ->
                            Json.Encode.bool value
                    )
                )
                rec.dot_approved
            , Just ( "ids", Json.Encode.list Json.Encode.int rec.ids )
            , Maybe.map
                (\mapUnpack -> ( "microster", Json.Encode.bool mapUnpack ))
                rec.microster
            , Maybe.map
                (\mapUnpack ->
                    ( "reg_approved"
                    , case mapUnpack of
                        OpenApi.Common.Null ->
                            Json.Encode.null

                        OpenApi.Common.Present value ->
                            Json.Encode.bool value
                    )
                )
                rec.reg_approved
            ]
        )


encodePreviewOut : Radscheduler.Types.PreviewOut -> Json.Encode.Value
encodePreviewOut rec =
    Json.Encode.object
        [ ( "checked_to"
          , case rec.checked_to of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    OpenApi.Common.encodeStringDate value
          )
        , ( "gaps", Json.Encode.list encodeGapOut rec.gaps )
        , ( "leave_hidden", Json.Encode.int rec.leave_hidden )
        , ( "leave_shown", Json.Encode.int rec.leave_shown )
        , ( "leave_waiting", Json.Encode.int rec.leave_waiting )
        , ( "shifts_hidden", Json.Encode.int rec.shifts_hidden )
        , ( "shifts_shown", Json.Encode.int rec.shifts_shown )
        , ( "violations", Json.Encode.list encodeViolationOut rec.violations )
        ]


encodePublishedRange : Radscheduler.Types.PublishedRange -> Json.Encode.Value
encodePublishedRange rec =
    Json.Encode.object
        [ ( "end", OpenApi.Common.encodeStringDate rec.end )
        , ( "start", OpenApi.Common.encodeStringDate rec.start )
        ]


encodeRegistrarOut : Radscheduler.Types.RegistrarOut -> Json.Encode.Value
encodeRegistrarOut rec =
    Json.Encode.object
        [ ( "id", Json.Encode.int rec.id )
        , ( "name", Json.Encode.string rec.name )
        , ( "username", Json.Encode.string rec.username )
        , ( "year"
          , case rec.year of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    Json.Encode.int value
          )
        ]


encodeRequestChecksOut : Radscheduler.Types.RequestChecksOut -> Json.Encode.Value
encodeRequestChecksOut rec =
    Json.Encode.object
        [ ( "away", Json.Encode.float rec.away )
        , ( "breaks", Json.Encode.int rec.breaks )
        , ( "days", Json.Encode.int rec.days )
        , ( "lost", Json.Encode.int rec.lost )
        , ( "roster", Json.Encode.int rec.roster )
        , ( "unrostered", Json.Encode.int rec.unrostered )
        ]


encodeRequestDayOut : Radscheduler.Types.RequestDayOut -> Json.Encode.Value
encodeRequestDayOut rec =
    Json.Encode.object
        [ ( "date", OpenApi.Common.encodeStringDate rec.date )
        , ( "lost"
          , Json.Encode.list (Json.Encode.list encodeShiftType) rec.lost
          )
        , ( "registrars", Json.Encode.int rec.registrars )
        , ( "rostered", Json.Encode.bool rec.rostered )
        , ( "short"
          , Json.Encode.list (Json.Encode.list encodeShiftType) rec.short
          )
        ]


encodeRequestRowOut : Radscheduler.Types.RequestRowOut -> Json.Encode.Value
encodeRequestRowOut rec =
    Json.Encode.object
        [ ( "asked"
          , case rec.asked of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    OpenApi.Common.encodeStringDateTime value
          )
        , ( "checks"
          , case rec.checks of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    encodeRequestChecksOut value
          )
        , ( "comment", Json.Encode.string rec.comment )
        , ( "days", Json.Encode.float rec.days )
        , ( "decided"
          , case rec.decided of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    OpenApi.Common.encodeStringDateTime value
          )
        , ( "end", OpenApi.Common.encodeStringDate rec.end )
        , ( "key", Json.Encode.int rec.key )
        , ( "leaves", Json.Encode.list encodeLeaveOut rec.leaves )
        , ( "portion", Json.Encode.string rec.portion )
        , ( "registrar", Json.Encode.int rec.registrar )
        , ( "start", OpenApi.Common.encodeStringDate rec.start )
        , ( "status", Json.Encode.string rec.status )
        , ( "type", encodeLeaveType rec.type_ )
        ]


encodeRosterOut : Radscheduler.Types.RosterOut -> Json.Encode.Value
encodeRosterOut rec =
    Json.Encode.object
        [ ( "checks", encodeChecksOut rec.checks )
        , ( "dates"
          , Json.Encode.list OpenApi.Common.encodeStringDate rec.dates
          )
        , ( "holidays", Json.Encode.list encodeHolidayOut rec.holidays )
        , ( "leaves", Json.Encode.list encodeLeaveOut rec.leaves )
        , ( "next", OpenApi.Common.encodeStringDate rec.next )
        , ( "prev", OpenApi.Common.encodeStringDate rec.prev )
        , ( "published"
          , case rec.published of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    encodePublishedRange value
          )
        , ( "registrars", Json.Encode.list encodeRegistrarOut rec.registrars )
        , ( "shifts", Json.Encode.list encodeShiftOut rec.shifts )
        , ( "statuses", Json.Encode.list encodeStatusOut rec.statuses )
        , ( "today", OpenApi.Common.encodeStringDate rec.today )
        , ( "week", OpenApi.Common.encodeStringDate rec.week )
        ]


encodeShiftCountsOut : Radscheduler.Types.ShiftCountsOut -> Json.Encode.Value
encodeShiftCountsOut rec =
    Json.Encode.object
        [ ( "periods", Json.Encode.list encodeShiftPeriodOut rec.periods )
        , ( "registrar", Json.Encode.int rec.registrar )
        ]


encodeShiftIn : Radscheduler.Types.ShiftIn -> Json.Encode.Value
encodeShiftIn rec =
    Json.Encode.object
        (List.filterMap
            Basics.identity
            [ Just ( "date", OpenApi.Common.encodeStringDate rec.date )
            , Maybe.map
                (\mapUnpack -> ( "extra_duty", Json.Encode.bool mapUnpack ))
                rec.extra_duty
            , Just ( "registrar", Json.Encode.int rec.registrar )
            , Just ( "type", encodeShiftType rec.type_ )
            ]
        )


encodeShiftOut : Radscheduler.Types.ShiftOut -> Json.Encode.Value
encodeShiftOut rec =
    Json.Encode.object
        [ ( "date", OpenApi.Common.encodeStringDate rec.date )
        , ( "extra_duty", Json.Encode.bool rec.extra_duty )
        , ( "id", Json.Encode.int rec.id )
        , ( "registrar"
          , case rec.registrar of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    Json.Encode.int value
          )
        , ( "type", encodeShiftType rec.type_ )
        ]


encodeShiftPatch : Radscheduler.Types.ShiftPatch -> Json.Encode.Value
encodeShiftPatch rec =
    Json.Encode.object
        (List.filterMap
            Basics.identity
            [ Maybe.map
                (\mapUnpack -> ( "extra_duty", Json.Encode.bool mapUnpack ))
                rec.extra_duty
            , Maybe.map
                (\mapUnpack -> ( "type", encodeShiftType mapUnpack ))
                rec.type_
            ]
        )


encodeShiftPeriodOut : Radscheduler.Types.ShiftPeriodOut -> Json.Encode.Value
encodeShiftPeriodOut rec =
    Json.Encode.object
        [ ( "end", OpenApi.Common.encodeStringDate rec.end )
        , ( "name", Json.Encode.string rec.name )
        , ( "peers", Json.Encode.int rec.peers )
        , ( "shifts", Json.Encode.list encodeShiftTallyOut rec.shifts )
        , ( "start", OpenApi.Common.encodeStringDate rec.start )
        ]


encodeShiftTallyOut : Radscheduler.Types.ShiftTallyOut -> Json.Encode.Value
encodeShiftTallyOut rec =
    Json.Encode.object
        [ ( "count", Json.Encode.int rec.count )
        , ( "max"
          , case rec.max of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    Json.Encode.int value
          )
        , ( "mean"
          , case rec.mean of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    Json.Encode.float value
          )
        , ( "median"
          , case rec.median of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    Json.Encode.float value
          )
        , ( "min"
          , case rec.min of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    Json.Encode.int value
          )
        , ( "type", encodeShiftType rec.type_ )
        ]


encodeShiftType : Radscheduler.Types.ShiftType -> Json.Encode.Value
encodeShiftType rec =
    Json.Encode.string (Radscheduler.Types.shiftTypeToString rec)


encodeStatusOut : Radscheduler.Types.StatusOut -> Json.Encode.Value
encodeStatusOut rec =
    Json.Encode.object
        [ ( "comment", Json.Encode.string rec.comment )
        , ( "end", OpenApi.Common.encodeStringDate rec.end )
        , ( "id", Json.Encode.int rec.id )
        , ( "registrar", Json.Encode.int rec.registrar )
        , ( "shift_types", Json.Encode.list encodeShiftType rec.shift_types )
        , ( "start", OpenApi.Common.encodeStringDate rec.start )
        , ( "type", encodeStatusType rec.type_ )
        , ( "weekdays", Json.Encode.list Json.Encode.int rec.weekdays )
        ]


encodeStatusType : Radscheduler.Types.StatusType -> Json.Encode.Value
encodeStatusType rec =
    Json.Encode.string (Radscheduler.Types.statusTypeToString rec)


encodeViolationOut : Radscheduler.Types.ViolationOut -> Json.Encode.Value
encodeViolationOut rec =
    Json.Encode.object
        [ ( "clause"
          , case rec.clause of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    Json.Encode.string value
          )
        , ( "dates"
          , Json.Encode.list OpenApi.Common.encodeStringDate rec.dates
          )
        , ( "message", Json.Encode.string rec.message )
        , ( "registrar", Json.Encode.int rec.registrar )
        , ( "rule", Json.Encode.string rec.rule )
        , ( "variance"
          , case rec.variance of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    Json.Encode.string value
          )
        ]


encodeWaitingCountsOut : Radscheduler.Types.WaitingCountsOut -> Json.Encode.Value
encodeWaitingCountsOut rec =
    Json.Encode.object
        [ ( "all", Json.Encode.int rec.all )
        , ( "mine"
          , case rec.mine of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    Json.Encode.int value
          )
        ]


encodeWorkloadOut : Radscheduler.Types.WorkloadOut -> Json.Encode.Value
encodeWorkloadOut rec =
    Json.Encode.object
        [ ( "load", Json.Encode.float rec.load )
        , ( "registrar", Json.Encode.int rec.registrar )
        ]


decodeAwayOut : Json.Decode.Decoder Radscheduler.Types.AwayOut
decodeAwayOut =
    Json.Decode.succeed
        (\approved date portion registrar type_ ->
            { approved = approved
            , date = date
            , portion = portion
            , registrar = registrar
            , type_ = type_
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "approved" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "date" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "portion" Json.Decode.string)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "registrar" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "type" decodeLeaveType)


decodeChecksOut : Json.Decode.Decoder Radscheduler.Types.ChecksOut
decodeChecksOut =
    Json.Decode.succeed
        (\variances violations workload ->
            { variances = variances
            , violations = violations
            , workload = workload
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "variances"
                (Json.Decode.list decodeViolationOut)
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "violations"
                (Json.Decode.list decodeViolationOut)
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "workload"
                (Json.Decode.list decodeWorkloadOut)
            )


decodeErrorOut : Json.Decode.Decoder Radscheduler.Types.ErrorOut
decodeErrorOut =
    Json.Decode.succeed (\detail -> { detail = detail })
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "detail" Json.Decode.string)


decodeFullCalendarHolidaySchema : Json.Decode.Decoder Radscheduler.Types.FullCalendarHolidaySchema
decodeFullCalendarHolidaySchema =
    Json.Decode.succeed
        (\allDay event_type id start title ->
            { allDay = allDay
            , event_type = event_type
            , id = id
            , start = start
            , title = title
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField "allDay" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField
                "event_type"
                Json.Decode.string
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField "id" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "start" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "title" Json.Decode.string)


decodeFullCalendarLeaveSchema : Json.Decode.Decoder Radscheduler.Types.FullCalendarLeaveSchema
decodeFullCalendarLeaveSchema =
    Json.Decode.succeed
        (\allDay event_type id start title ->
            { allDay = allDay
            , event_type = event_type
            , id = id
            , start = start
            , title = title
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField "allDay" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField
                "event_type"
                Json.Decode.string
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField
                "id"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.int
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "start" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "title" Json.Decode.string)


decodeFullCalendarShiftSchema : Json.Decode.Decoder Radscheduler.Types.FullCalendarShiftSchema
decodeFullCalendarShiftSchema =
    Json.Decode.succeed
        (\allDay event_type id start title ->
            { allDay = allDay
            , event_type = event_type
            , id = id
            , start = start
            , title = title
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField "allDay" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField
                "event_type"
                Json.Decode.string
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField
                "id"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.int
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "start" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "title" Json.Decode.string)


decodeGapOut : Json.Decode.Decoder Radscheduler.Types.GapOut
decodeGapOut =
    Json.Decode.succeed (\date needs -> { date = date, needs = needs })
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "date" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "needs"
                (Json.Decode.list (Json.Decode.list decodeShiftType))
            )


decodeHolidayOut : Json.Decode.Decoder Radscheduler.Types.HolidayOut
decodeHolidayOut =
    Json.Decode.succeed (\date name -> { date = date, name = name })
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "date" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "name" Json.Decode.string)


decodeLeaveOut : Json.Decode.Decoder Radscheduler.Types.LeaveOut
decodeLeaveOut =
    Json.Decode.succeed
        (\cancelled comment created date dot_approved dot_decided_at dot_decided_by id last_edited microster portion printed reg_approved reg_decided_at reg_decided_by registrar type_ ->
            { cancelled = cancelled
            , comment = comment
            , created = created
            , date = date
            , dot_approved = dot_approved
            , dot_decided_at = dot_decided_at
            , dot_decided_by = dot_decided_by
            , id = id
            , last_edited = last_edited
            , microster = microster
            , portion = portion
            , printed = printed
            , reg_approved = reg_approved
            , reg_decided_at = reg_decided_at
            , reg_decided_by = reg_decided_by
            , registrar = registrar
            , type_ = type_
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "cancelled" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "comment" Json.Decode.string)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "created" OpenApi.Common.decodeStringDateTime)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "date" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "dot_approved"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.bool
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "dot_decided_at"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        OpenApi.Common.decodeStringDateTime
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "dot_decided_by"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.string
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "id" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "last_edited"
                OpenApi.Common.decodeStringDateTime
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "microster" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "portion" Json.Decode.string)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "printed" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "reg_approved"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.bool
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "reg_decided_at"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        OpenApi.Common.decodeStringDateTime
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "reg_decided_by"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.string
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "registrar" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "type" decodeLeaveType)


decodeLeaveOverviewOut : Json.Decode.Decoder Radscheduler.Types.LeaveOverviewOut
decodeLeaveOverviewOut =
    Json.Decode.succeed
        (\registrars rows total ->
            { registrars = registrars, rows = rows, total = total }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "registrars"
                (Json.Decode.list decodeRegistrarOut)
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "rows" (Json.Decode.list decodeRequestRowOut))
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "total" Json.Decode.int)


decodeLeavePatch : Json.Decode.Decoder Radscheduler.Types.LeavePatch
decodeLeavePatch =
    Json.Decode.succeed
        (\cancelled dot_approved microster reg_approved ->
            { cancelled = cancelled
            , dot_approved = dot_approved
            , microster = microster
            , reg_approved = reg_approved
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField "cancelled" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField
                "dot_approved"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.bool
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField "microster" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField
                "reg_approved"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.bool
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )


decodeLeaveRequestOut : Json.Decode.Decoder Radscheduler.Types.LeaveRequestOut
decodeLeaveRequestOut =
    Json.Decode.succeed
        (\asked away dates days existing_violations leaves other_leave registrar shifts violations years ->
            { asked = asked
            , away = away
            , dates = dates
            , days = days
            , existing_violations = existing_violations
            , leaves = leaves
            , other_leave = other_leave
            , registrar = registrar
            , shifts = shifts
            , violations = violations
            , years = years
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "asked"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        OpenApi.Common.decodeStringDateTime
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "away" (Json.Decode.list decodeAwayOut))
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "dates"
                (Json.Decode.list OpenApi.Common.decodeStringDate)
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "days" (Json.Decode.list decodeRequestDayOut))
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "existing_violations"
                (Json.Decode.list decodeViolationOut)
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "leaves" (Json.Decode.list decodeLeaveOut))
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "other_leave"
                (Json.Decode.list decodeLeaveOut)
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "registrar" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "shifts" (Json.Decode.list decodeShiftOut))
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "violations"
                (Json.Decode.list decodeViolationOut)
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "years" (Json.Decode.list decodeLeaveYearOut))


decodeLeaveRequestsOut : Json.Decode.Decoder Radscheduler.Types.LeaveRequestsOut
decodeLeaveRequestsOut =
    Json.Decode.succeed
        (\holidays registrars requests total ->
            { holidays = holidays
            , registrars = registrars
            , requests = requests
            , total = total
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "holidays" (Json.Decode.list decodeHolidayOut))
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "registrars"
                (Json.Decode.list decodeRegistrarOut)
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "requests"
                (Json.Decode.list decodeLeaveRequestOut)
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "total" Json.Decode.int)


decodeLeaveTallyOut : Json.Decode.Decoder Radscheduler.Types.LeaveTallyOut
decodeLeaveTallyOut =
    Json.Decode.succeed
        (\approved request type_ waiting ->
            { approved = approved
            , request = request
            , type_ = type_
            , waiting = waiting
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "approved" Json.Decode.float)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "request" Json.Decode.float)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "type" decodeLeaveType)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "waiting" Json.Decode.float)


decodeLeaveType : Json.Decode.Decoder Radscheduler.Types.LeaveType
decodeLeaveType =
    Json.Decode.andThen
        (\andThenUnpack ->
            case Radscheduler.Types.leaveTypeFromString andThenUnpack of
                Maybe.Just a ->
                    Json.Decode.succeed a

                Maybe.Nothing ->
                    Json.Decode.fail
                        (andThenUnpack ++ " is not a valid LeaveType")
        )
        Json.Decode.string


decodeLeaveYearOut : Json.Decode.Decoder Radscheduler.Types.LeaveYearOut
decodeLeaveYearOut =
    Json.Decode.succeed
        (\end lead start types ->
            { end = end, lead = lead, start = start, types = types }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "end" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "lead" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "start" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "types" (Json.Decode.list decodeLeaveTallyOut))


decodeLeavesPatch : Json.Decode.Decoder Radscheduler.Types.LeavesPatch
decodeLeavesPatch =
    Json.Decode.succeed
        (\cancelled dot_approved ids microster reg_approved ->
            { cancelled = cancelled
            , dot_approved = dot_approved
            , ids = ids
            , microster = microster
            , reg_approved = reg_approved
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField "cancelled" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField
                "dot_approved"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.bool
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "ids" (Json.Decode.list Json.Decode.int))
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField "microster" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField
                "reg_approved"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.bool
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )


decodePreviewOut : Json.Decode.Decoder Radscheduler.Types.PreviewOut
decodePreviewOut =
    Json.Decode.succeed
        (\checked_to gaps leave_hidden leave_shown leave_waiting shifts_hidden shifts_shown violations ->
            { checked_to = checked_to
            , gaps = gaps
            , leave_hidden = leave_hidden
            , leave_shown = leave_shown
            , leave_waiting = leave_waiting
            , shifts_hidden = shifts_hidden
            , shifts_shown = shifts_shown
            , violations = violations
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "checked_to"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        OpenApi.Common.decodeStringDate
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "gaps" (Json.Decode.list decodeGapOut))
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "leave_hidden" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "leave_shown" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "leave_waiting" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "shifts_hidden" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "shifts_shown" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "violations"
                (Json.Decode.list decodeViolationOut)
            )


decodePublishedRange : Json.Decode.Decoder Radscheduler.Types.PublishedRange
decodePublishedRange =
    Json.Decode.succeed (\end start -> { end = end, start = start })
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "end" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "start" OpenApi.Common.decodeStringDate)


decodeRegistrarOut : Json.Decode.Decoder Radscheduler.Types.RegistrarOut
decodeRegistrarOut =
    Json.Decode.succeed
        (\id name username year ->
            { id = id, name = name, username = username, year = year }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "id" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "name" Json.Decode.string)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "username" Json.Decode.string)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "year"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.int
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )


decodeRequestChecksOut : Json.Decode.Decoder Radscheduler.Types.RequestChecksOut
decodeRequestChecksOut =
    Json.Decode.succeed
        (\away breaks days lost roster unrostered ->
            { away = away
            , breaks = breaks
            , days = days
            , lost = lost
            , roster = roster
            , unrostered = unrostered
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "away" Json.Decode.float)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "breaks" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "days" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "lost" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "roster" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "unrostered" Json.Decode.int)


decodeRequestDayOut : Json.Decode.Decoder Radscheduler.Types.RequestDayOut
decodeRequestDayOut =
    Json.Decode.succeed
        (\date lost registrars rostered short ->
            { date = date
            , lost = lost
            , registrars = registrars
            , rostered = rostered
            , short = short
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "date" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "lost"
                (Json.Decode.list (Json.Decode.list decodeShiftType))
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "registrars" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "rostered" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "short"
                (Json.Decode.list (Json.Decode.list decodeShiftType))
            )


decodeRequestRowOut : Json.Decode.Decoder Radscheduler.Types.RequestRowOut
decodeRequestRowOut =
    Json.Decode.succeed
        (\asked checks comment days decided end key leaves portion registrar start status type_ ->
            { asked = asked
            , checks = checks
            , comment = comment
            , days = days
            , decided = decided
            , end = end
            , key = key
            , leaves = leaves
            , portion = portion
            , registrar = registrar
            , start = start
            , status = status
            , type_ = type_
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "asked"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        OpenApi.Common.decodeStringDateTime
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "checks"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        decodeRequestChecksOut
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "comment" Json.Decode.string)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "days" Json.Decode.float)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "decided"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        OpenApi.Common.decodeStringDateTime
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "end" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "key" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "leaves" (Json.Decode.list decodeLeaveOut))
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "portion" Json.Decode.string)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "registrar" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "start" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "status" Json.Decode.string)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "type" decodeLeaveType)


decodeRosterOut : Json.Decode.Decoder Radscheduler.Types.RosterOut
decodeRosterOut =
    Json.Decode.succeed
        (\checks dates holidays leaves next prev published registrars shifts statuses today week ->
            { checks = checks
            , dates = dates
            , holidays = holidays
            , leaves = leaves
            , next = next
            , prev = prev
            , published = published
            , registrars = registrars
            , shifts = shifts
            , statuses = statuses
            , today = today
            , week = week
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "checks" decodeChecksOut)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "dates"
                (Json.Decode.list OpenApi.Common.decodeStringDate)
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "holidays" (Json.Decode.list decodeHolidayOut))
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "leaves" (Json.Decode.list decodeLeaveOut))
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "next" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "prev" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "published"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        decodePublishedRange
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "registrars"
                (Json.Decode.list decodeRegistrarOut)
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "shifts" (Json.Decode.list decodeShiftOut))
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "statuses" (Json.Decode.list decodeStatusOut))
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "today" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "week" OpenApi.Common.decodeStringDate)


decodeShiftCountsOut : Json.Decode.Decoder Radscheduler.Types.ShiftCountsOut
decodeShiftCountsOut =
    Json.Decode.succeed
        (\periods registrar -> { periods = periods, registrar = registrar })
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "periods"
                (Json.Decode.list decodeShiftPeriodOut)
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "registrar" Json.Decode.int)


decodeShiftIn : Json.Decode.Decoder Radscheduler.Types.ShiftIn
decodeShiftIn =
    Json.Decode.succeed
        (\date extra_duty registrar type_ ->
            { date = date
            , extra_duty = extra_duty
            , registrar = registrar
            , type_ = type_
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "date" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField "extra_duty" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "registrar" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "type" decodeShiftType)


decodeShiftOut : Json.Decode.Decoder Radscheduler.Types.ShiftOut
decodeShiftOut =
    Json.Decode.succeed
        (\date extra_duty id registrar type_ ->
            { date = date
            , extra_duty = extra_duty
            , id = id
            , registrar = registrar
            , type_ = type_
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "date" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "extra_duty" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "id" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "registrar"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.int
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "type" decodeShiftType)


decodeShiftPatch : Json.Decode.Decoder Radscheduler.Types.ShiftPatch
decodeShiftPatch =
    Json.Decode.succeed
        (\extra_duty type_ -> { extra_duty = extra_duty, type_ = type_ })
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField "extra_duty" Json.Decode.bool)
        |> OpenApi.Common.jsonDecodeAndMap
            (OpenApi.Common.decodeOptionalField "type" decodeShiftType)


decodeShiftPeriodOut : Json.Decode.Decoder Radscheduler.Types.ShiftPeriodOut
decodeShiftPeriodOut =
    Json.Decode.succeed
        (\end name peers shifts start ->
            { end = end
            , name = name
            , peers = peers
            , shifts = shifts
            , start = start
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "end" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "name" Json.Decode.string)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "peers" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "shifts"
                (Json.Decode.list decodeShiftTallyOut)
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "start" OpenApi.Common.decodeStringDate)


decodeShiftTallyOut : Json.Decode.Decoder Radscheduler.Types.ShiftTallyOut
decodeShiftTallyOut =
    Json.Decode.succeed
        (\count max mean median min type_ ->
            { count = count
            , max = max
            , mean = mean
            , median = median
            , min = min
            , type_ = type_
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "count" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "max"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.int
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "mean"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.float
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "median"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.float
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "min"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.int
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "type" decodeShiftType)


decodeShiftType : Json.Decode.Decoder Radscheduler.Types.ShiftType
decodeShiftType =
    Json.Decode.andThen
        (\andThenUnpack ->
            case Radscheduler.Types.shiftTypeFromString andThenUnpack of
                Maybe.Just a ->
                    Json.Decode.succeed a

                Maybe.Nothing ->
                    Json.Decode.fail
                        (andThenUnpack ++ " is not a valid ShiftType")
        )
        Json.Decode.string


decodeStatusOut : Json.Decode.Decoder Radscheduler.Types.StatusOut
decodeStatusOut =
    Json.Decode.succeed
        (\comment end id registrar shift_types start type_ weekdays ->
            { comment = comment
            , end = end
            , id = id
            , registrar = registrar
            , shift_types = shift_types
            , start = start
            , type_ = type_
            , weekdays = weekdays
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "comment" Json.Decode.string)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "end" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "id" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "registrar" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "shift_types"
                (Json.Decode.list decodeShiftType)
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "start" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "type" decodeStatusType)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "weekdays" (Json.Decode.list Json.Decode.int))


decodeStatusType : Json.Decode.Decoder Radscheduler.Types.StatusType
decodeStatusType =
    Json.Decode.andThen
        (\andThenUnpack ->
            case Radscheduler.Types.statusTypeFromString andThenUnpack of
                Maybe.Just a ->
                    Json.Decode.succeed a

                Maybe.Nothing ->
                    Json.Decode.fail
                        (andThenUnpack ++ " is not a valid StatusType")
        )
        Json.Decode.string


decodeViolationOut : Json.Decode.Decoder Radscheduler.Types.ViolationOut
decodeViolationOut =
    Json.Decode.succeed
        (\clause dates message registrar rule variance ->
            { clause = clause
            , dates = dates
            , message = message
            , registrar = registrar
            , rule = rule
            , variance = variance
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "clause"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.string
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "dates"
                (Json.Decode.list OpenApi.Common.decodeStringDate)
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "message" Json.Decode.string)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "registrar" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "rule" Json.Decode.string)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "variance"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.string
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )


decodeWaitingCountsOut : Json.Decode.Decoder Radscheduler.Types.WaitingCountsOut
decodeWaitingCountsOut =
    Json.Decode.succeed (\all mine -> { all = all, mine = mine })
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "all" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "mine"
                (Json.Decode.oneOf
                    [ Json.Decode.map
                        OpenApi.Common.Present
                        Json.Decode.int
                    , Json.Decode.null OpenApi.Common.Null
                    ]
                )
            )


decodeWorkloadOut : Json.Decode.Decoder Radscheduler.Types.WorkloadOut
decodeWorkloadOut =
    Json.Decode.succeed
        (\load registrar -> { load = load, registrar = registrar })
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "load" Json.Decode.float)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "registrar" Json.Decode.int)
