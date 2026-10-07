module Radscheduler.Api exposing
    ( addShift, changeLeave, changeLeaves, changeShift, deleteShift, getChecks
    , getRoster, holidayEvents, leaveEvents, previewPublished, setPublished, shiftEvents
    )

{-|


## Operations

@docs addShift, changeLeave, changeLeaves, changeShift, deleteShift, getChecks
@docs getRoster, holidayEvents, leaveEvents, previewPublished, setPublished, shiftEvents

-}

import Date
import Dict
import Http
import Json.Decode
import Json.Encode
import OpenApi.Common
import Radscheduler.Json
import Radscheduler.Types
import Url.Builder


{-| Add Shift
-}
addShift :
    { authorization : { x_csrftoken : String }
    , toMsg :
        Result (OpenApi.Common.Error e String) Radscheduler.Types.ShiftOut
        -> msg
    , body : Radscheduler.Types.ShiftIn
    }
    -> Cmd msg
addShift config =
    Http.request
        { url = Url.Builder.absolute [ "api", "editor", "shifts" ] []
        , method = "POST"
        , headers =
            [ Http.header "X-CSRFToken" config.authorization.x_csrftoken ]
        , expect =
            OpenApi.Common.expectJsonCustom
                (Dict.fromList [])
                Radscheduler.Json.decodeShiftOut
                config.toMsg
        , body = Http.jsonBody (Radscheduler.Json.encodeShiftIn config.body)
        , timeout = Nothing
        , tracker = Nothing
        }


{-| Change Leave
-}
changeLeave :
    { authorization : { x_csrftoken : String }
    , toMsg :
        Result (OpenApi.Common.Error e String) Radscheduler.Types.LeaveOut
        -> msg
    , body : Radscheduler.Types.LeavePatch
    , params : { leave_id : Int }
    }
    -> Cmd msg
changeLeave config =
    Http.request
        { url =
            Url.Builder.absolute
                [ "api"
                , "editor"
                , "leaves"
                , String.fromInt config.params.leave_id
                ]
                []
        , method = "PATCH"
        , headers =
            [ Http.header "X-CSRFToken" config.authorization.x_csrftoken ]
        , expect =
            OpenApi.Common.expectJsonCustom
                (Dict.fromList [])
                Radscheduler.Json.decodeLeaveOut
                config.toMsg
        , body = Http.jsonBody (Radscheduler.Json.encodeLeavePatch config.body)
        , timeout = Nothing
        , tracker = Nothing
        }


{-| Change Leaves
-}
changeLeaves :
    { authorization : { x_csrftoken : String }
    , toMsg :
        Result (OpenApi.Common.Error e String) (List Radscheduler.Types.LeaveOut)
        -> msg
    , body : Radscheduler.Types.LeavesPatch
    }
    -> Cmd msg
changeLeaves config =
    Http.request
        { url = Url.Builder.absolute [ "api", "editor", "leaves" ] []
        , method = "PATCH"
        , headers =
            [ Http.header "X-CSRFToken" config.authorization.x_csrftoken ]
        , expect =
            OpenApi.Common.expectJsonCustom
                (Dict.fromList [])
                (Json.Decode.list Radscheduler.Json.decodeLeaveOut)
                config.toMsg
        , body = Http.jsonBody (Radscheduler.Json.encodeLeavesPatch config.body)
        , timeout = Nothing
        , tracker = Nothing
        }


{-| Change Shift
-}
changeShift :
    { authorization : { x_csrftoken : String }
    , toMsg :
        Result (OpenApi.Common.Error e String) Radscheduler.Types.ShiftOut
        -> msg
    , body : Radscheduler.Types.ShiftPatch
    , params : { shift_id : Int }
    }
    -> Cmd msg
changeShift config =
    Http.request
        { url =
            Url.Builder.absolute
                [ "api"
                , "editor"
                , "shifts"
                , String.fromInt config.params.shift_id
                ]
                []
        , method = "PATCH"
        , headers =
            [ Http.header "X-CSRFToken" config.authorization.x_csrftoken ]
        , expect =
            OpenApi.Common.expectJsonCustom
                (Dict.fromList [])
                Radscheduler.Json.decodeShiftOut
                config.toMsg
        , body = Http.jsonBody (Radscheduler.Json.encodeShiftPatch config.body)
        , timeout = Nothing
        , tracker = Nothing
        }


{-| Delete Shift
-}
deleteShift :
    { authorization : { x_csrftoken : String }
    , toMsg :
        Result (OpenApi.Common.Error e String) Radscheduler.Types.ShiftOut
        -> msg
    , params : { shift_id : Int }
    }
    -> Cmd msg
deleteShift config =
    Http.request
        { url =
            Url.Builder.absolute
                [ "api"
                , "editor"
                , "shifts"
                , String.fromInt config.params.shift_id
                ]
                []
        , method = "DELETE"
        , headers =
            [ Http.header "X-CSRFToken" config.authorization.x_csrftoken ]
        , expect =
            OpenApi.Common.expectJsonCustom
                (Dict.fromList [])
                Radscheduler.Json.decodeShiftOut
                config.toMsg
        , body = Http.emptyBody
        , timeout = Nothing
        , tracker = Nothing
        }


{-| Get Checks

The rule breaks and workload alone, for refreshing them after a change.

-}
getChecks :
    { authorization : { x_csrftoken : String }
    , toMsg :
        Result (OpenApi.Common.Error e String) Radscheduler.Types.ChecksOut
        -> msg
    , params : { week : Date.Date }
    }
    -> Cmd msg
getChecks config =
    Http.request
        { url =
            Url.Builder.absolute
                [ "api", "editor", "roster", "checks" ]
                (List.filterMap
                    Basics.identity
                    [ Just
                        (Url.Builder.string
                            "week"
                            (OpenApi.Common.toParamStringStringDate
                                config.params.week
                            )
                        )
                    ]
                )
        , method = "GET"
        , headers =
            [ Http.header "X-CSRFToken" config.authorization.x_csrftoken ]
        , expect =
            OpenApi.Common.expectJsonCustom
                (Dict.fromList [])
                Radscheduler.Json.decodeChecksOut
                config.toMsg
        , body = Http.emptyBody
        , timeout = Nothing
        , tracker = Nothing
        }


{-| Get Roster
-}
getRoster :
    { authorization : { x_csrftoken : String }
    , toMsg :
        Result (OpenApi.Common.Error e String) Radscheduler.Types.RosterOut
        -> msg
    , params : { week : Date.Date }
    }
    -> Cmd msg
getRoster config =
    Http.request
        { url =
            Url.Builder.absolute
                [ "api", "editor", "roster" ]
                (List.filterMap
                    Basics.identity
                    [ Just
                        (Url.Builder.string
                            "week"
                            (OpenApi.Common.toParamStringStringDate
                                config.params.week
                            )
                        )
                    ]
                )
        , method = "GET"
        , headers =
            [ Http.header "X-CSRFToken" config.authorization.x_csrftoken ]
        , expect =
            OpenApi.Common.expectJsonCustom
                (Dict.fromList [])
                Radscheduler.Json.decodeRosterOut
                config.toMsg
        , body = Http.emptyBody
        , timeout = Nothing
        , tracker = Nothing
        }


{-| Holiday Events
-}
holidayEvents :
    { toMsg :
        Result (OpenApi.Common.Error e String) (List Radscheduler.Types.FullCalendarHolidaySchema)
        -> msg
    , params : { start : Date.Date, end : Date.Date }
    }
    -> Cmd msg
holidayEvents config =
    Http.request
        { url =
            Url.Builder.absolute
                [ "api", "calendar", "holidays" ]
                (List.filterMap
                    Basics.identity
                    [ Just
                        (Url.Builder.string
                            "start"
                            (OpenApi.Common.toParamStringStringDate
                                config.params.start
                            )
                        )
                    , Just
                        (Url.Builder.string
                            "end"
                            (OpenApi.Common.toParamStringStringDate
                                config.params.end
                            )
                        )
                    ]
                )
        , method = "GET"
        , headers = []
        , expect =
            OpenApi.Common.expectJsonCustom
                (Dict.fromList [])
                (Json.Decode.list
                    Radscheduler.Json.decodeFullCalendarHolidaySchema
                )
                config.toMsg
        , body = Http.emptyBody
        , timeout = Nothing
        , tracker = Nothing
        }


{-| Leave Events
-}
leaveEvents :
    { toMsg :
        Result (OpenApi.Common.Error e String) (List Radscheduler.Types.FullCalendarLeaveSchema)
        -> msg
    , params : { start : Date.Date, end : Date.Date }
    }
    -> Cmd msg
leaveEvents config =
    Http.request
        { url =
            Url.Builder.absolute
                [ "api", "calendar", "leaves" ]
                (List.filterMap
                    Basics.identity
                    [ Just
                        (Url.Builder.string
                            "start"
                            (OpenApi.Common.toParamStringStringDate
                                config.params.start
                            )
                        )
                    , Just
                        (Url.Builder.string
                            "end"
                            (OpenApi.Common.toParamStringStringDate
                                config.params.end
                            )
                        )
                    ]
                )
        , method = "GET"
        , headers = []
        , expect =
            OpenApi.Common.expectJsonCustom
                (Dict.fromList [])
                (Json.Decode.list
                    Radscheduler.Json.decodeFullCalendarLeaveSchema
                )
                config.toMsg
        , body = Http.emptyBody
        , timeout = Nothing
        , tracker = Nothing
        }


{-| Preview Published
-}
previewPublished :
    { authorization : { x_csrftoken : String }
    , toMsg :
        Result (OpenApi.Common.Error e String) Radscheduler.Types.PreviewOut
        -> msg
    , params : { start : Date.Date, end : Date.Date }
    }
    -> Cmd msg
previewPublished config =
    Http.request
        { url =
            Url.Builder.absolute
                [ "api", "editor", "published", "preview" ]
                (List.filterMap
                    Basics.identity
                    [ Just
                        (Url.Builder.string
                            "start"
                            (OpenApi.Common.toParamStringStringDate
                                config.params.start
                            )
                        )
                    , Just
                        (Url.Builder.string
                            "end"
                            (OpenApi.Common.toParamStringStringDate
                                config.params.end
                            )
                        )
                    ]
                )
        , method = "GET"
        , headers =
            [ Http.header "X-CSRFToken" config.authorization.x_csrftoken ]
        , expect =
            OpenApi.Common.expectJsonCustom
                (Dict.fromList [])
                Radscheduler.Json.decodePreviewOut
                config.toMsg
        , body = Http.emptyBody
        , timeout = Nothing
        , tracker = Nothing
        }


{-| Set Published
-}
setPublished :
    { authorization : { x_csrftoken : String }
    , toMsg :
        Result (OpenApi.Common.Error Radscheduler.Types.ErrorOut String) Radscheduler.Types.PublishedRange
        -> msg
    , body : Radscheduler.Types.PublishedRange
    }
    -> Cmd msg
setPublished config =
    Http.request
        { url = Url.Builder.absolute [ "api", "editor", "published" ] []
        , method = "PUT"
        , headers =
            [ Http.header "X-CSRFToken" config.authorization.x_csrftoken ]
        , expect =
            OpenApi.Common.expectJsonCustom
                (Dict.fromList [ ( "422", Radscheduler.Json.decodeErrorOut ) ])
                Radscheduler.Json.decodePublishedRange
                config.toMsg
        , body =
            Http.jsonBody (Radscheduler.Json.encodePublishedRange config.body)
        , timeout = Nothing
        , tracker = Nothing
        }


{-| Shift Events
-}
shiftEvents :
    { toMsg :
        Result (OpenApi.Common.Error e String) (List Radscheduler.Types.FullCalendarShiftSchema)
        -> msg
    , params : { start : Date.Date, end : Date.Date }
    }
    -> Cmd msg
shiftEvents config =
    Http.request
        { url =
            Url.Builder.absolute
                [ "api", "calendar", "shifts" ]
                (List.filterMap
                    Basics.identity
                    [ Just
                        (Url.Builder.string
                            "start"
                            (OpenApi.Common.toParamStringStringDate
                                config.params.start
                            )
                        )
                    , Just
                        (Url.Builder.string
                            "end"
                            (OpenApi.Common.toParamStringStringDate
                                config.params.end
                            )
                        )
                    ]
                )
        , method = "GET"
        , headers = []
        , expect =
            OpenApi.Common.expectJsonCustom
                (Dict.fromList [])
                (Json.Decode.list
                    Radscheduler.Json.decodeFullCalendarShiftSchema
                )
                config.toMsg
        , body = Http.emptyBody
        , timeout = Nothing
        , tracker = Nothing
        }
