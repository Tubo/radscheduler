module Radscheduler.Json exposing
    ( encodeErrorOut, encodeFullCalendarHolidaySchema, encodeFullCalendarLeaveSchema, encodeFullCalendarShiftSchema, encodeHolidayOut, encodeLeaveOut
    , encodeLeavePatch, encodeLeaveType, encodePreviewOut, encodePublishedRange, encodeRegistrarOut, encodeRosterOut
    , encodeShiftIn, encodeShiftOut, encodeShiftPatch, encodeShiftType
    , decodeErrorOut, decodeFullCalendarHolidaySchema, decodeFullCalendarLeaveSchema, decodeFullCalendarShiftSchema, decodeHolidayOut, decodeLeaveOut
    , decodeLeavePatch, decodeLeaveType, decodePreviewOut, decodePublishedRange, decodeRegistrarOut, decodeRosterOut
    , decodeShiftIn, decodeShiftOut, decodeShiftPatch, decodeShiftType
    )

{-|


## Encoders

@docs encodeErrorOut, encodeFullCalendarHolidaySchema, encodeFullCalendarLeaveSchema, encodeFullCalendarShiftSchema, encodeHolidayOut, encodeLeaveOut
@docs encodeLeavePatch, encodeLeaveType, encodePreviewOut, encodePublishedRange, encodeRegistrarOut, encodeRosterOut
@docs encodeShiftIn, encodeShiftOut, encodeShiftPatch, encodeShiftType


## Decoders

@docs decodeErrorOut, decodeFullCalendarHolidaySchema, decodeFullCalendarLeaveSchema, decodeFullCalendarShiftSchema, decodeHolidayOut, decodeLeaveOut
@docs decodeLeavePatch, decodeLeaveType, decodePreviewOut, decodePublishedRange, decodeRegistrarOut, decodeRosterOut
@docs decodeShiftIn, decodeShiftOut, decodeShiftPatch, decodeShiftType

-}

import Date
import Json.Decode
import Json.Encode
import OpenApi.Common
import Radscheduler.Types
import Time


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
        , ( "id", Json.Encode.int rec.id )
        , ( "last_edited", OpenApi.Common.encodeStringDateTime rec.last_edited )
        , ( "portion", Json.Encode.string rec.portion )
        , ( "reg_approved"
          , case rec.reg_approved of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    Json.Encode.bool value
          )
        , ( "registrar", Json.Encode.int rec.registrar )
        , ( "type", encodeLeaveType rec.type_ )
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


encodeLeaveType : Radscheduler.Types.LeaveType -> Json.Encode.Value
encodeLeaveType rec =
    Json.Encode.string (Radscheduler.Types.leaveTypeToString rec)


encodePreviewOut : Radscheduler.Types.PreviewOut -> Json.Encode.Value
encodePreviewOut rec =
    Json.Encode.object
        [ ( "leave_hidden", Json.Encode.int rec.leave_hidden )
        , ( "leave_shown", Json.Encode.int rec.leave_shown )
        , ( "shifts_hidden", Json.Encode.int rec.shifts_hidden )
        , ( "shifts_shown", Json.Encode.int rec.shifts_shown )
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
        , ( "username", Json.Encode.string rec.username )
        , ( "year"
          , case rec.year of
                OpenApi.Common.Null ->
                    Json.Encode.null

                OpenApi.Common.Present value ->
                    Json.Encode.int value
          )
        ]


encodeRosterOut : Radscheduler.Types.RosterOut -> Json.Encode.Value
encodeRosterOut rec =
    Json.Encode.object
        [ ( "dates"
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
        , ( "today", OpenApi.Common.encodeStringDate rec.today )
        , ( "week", OpenApi.Common.encodeStringDate rec.week )
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


encodeShiftType : Radscheduler.Types.ShiftType -> Json.Encode.Value
encodeShiftType rec =
    Json.Encode.string (Radscheduler.Types.shiftTypeToString rec)


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
        (\cancelled comment created date dot_approved id last_edited portion reg_approved registrar type_ ->
            { cancelled = cancelled
            , comment = comment
            , created = created
            , date = date
            , dot_approved = dot_approved
            , id = id
            , last_edited = last_edited
            , portion = portion
            , reg_approved = reg_approved
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
            (Json.Decode.field "id" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field
                "last_edited"
                OpenApi.Common.decodeStringDateTime
            )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "portion" Json.Decode.string)
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
            (Json.Decode.field "registrar" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "type" decodeLeaveType)


decodeLeavePatch : Json.Decode.Decoder Radscheduler.Types.LeavePatch
decodeLeavePatch =
    Json.Decode.succeed
        (\cancelled dot_approved reg_approved ->
            { cancelled = cancelled
            , dot_approved = dot_approved
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


decodePreviewOut : Json.Decode.Decoder Radscheduler.Types.PreviewOut
decodePreviewOut =
    Json.Decode.succeed
        (\leave_hidden leave_shown shifts_hidden shifts_shown ->
            { leave_hidden = leave_hidden
            , leave_shown = leave_shown
            , shifts_hidden = shifts_hidden
            , shifts_shown = shifts_shown
            }
        )
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "leave_hidden" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "leave_shown" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "shifts_hidden" Json.Decode.int)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "shifts_shown" Json.Decode.int)


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
        (\id username year -> { id = id, username = username, year = year })
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "id" Json.Decode.int)
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


decodeRosterOut : Json.Decode.Decoder Radscheduler.Types.RosterOut
decodeRosterOut =
    Json.Decode.succeed
        (\dates holidays leaves next prev published registrars shifts today week ->
            { dates = dates
            , holidays = holidays
            , leaves = leaves
            , next = next
            , prev = prev
            , published = published
            , registrars = registrars
            , shifts = shifts
            , today = today
            , week = week
            }
        )
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
            (Json.Decode.field "today" OpenApi.Common.decodeStringDate)
        |> OpenApi.Common.jsonDecodeAndMap
            (Json.Decode.field "week" OpenApi.Common.decodeStringDate)


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
