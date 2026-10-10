module LeaveFilters exposing
    ( Filters
    , Sort
    , Status
    , defaults
    , fromQuery
    , isDefault
    , sortByLeave
    , sorts
    , statusLabel
    , toQuery
    )

{-| Which leave requests the leave requests page lists, and in what order: the filters of its overview,
which approval mode reviews too. They are kept in the page's address, so a reload or a shared link opens the
same list, and sent to the API as its query (the lists comma-separated).
-}

import Dict
import Url


{-| "mine" (waiting on this user's decision), "waiting" (on anyone's), "approved", "declined", "cancelled"
or "any".
-}
type alias Status =
    String


{-| One of `sorts`.
-}
type alias Sort =
    String


type alias Filters =
    { status : Status

    -- ISO dates, empty for no limit: requests with any day between them.
    , start : String
    , end : String
    , years : List Int
    , types : List String
    , registrar : Maybe Int
    , sort : Sort
    }


{-| What the page opens on: what waits on the user, or on anyone for a user who decides none, soonest first.
-}
defaults : Bool -> Filters
defaults decides =
    { status =
        if decides then
            "mine"

        else
            "waiting"
    , start = ""
    , end = ""
    , years = []
    , types = []
    , registrar = Nothing
    , sort = "leave"
    }


isDefault : Bool -> Filters -> Bool
isDefault decides filters =
    filters == defaults decides


statusLabel : Status -> String
statusLabel status =
    case status of
        "mine" ->
            "Waiting on you"

        "waiting" ->
            "All waiting"

        "approved" ->
            "Approved"

        "declined" ->
            "Declined"

        "cancelled" ->
            "Cancelled"

        _ ->
            "Any status"


{-| The orders the overview offers, with their names.
-}
sorts : List ( Sort, String )
sorts =
    [ ( "leave", "Leave date, soonest first" )
    , ( "leave-desc", "Leave date, latest first" )
    , ( "asked-desc", "Asked, newest first" )
    , ( "asked", "Asked, oldest first" )
    , ( "decided-desc", "Decided, latest first" )
    , ( "registrar", "Registrar, A to Z" )
    , ( "length-desc", "Longest first" )
    ]


{-| Whether the list runs in order of leave date, so can be grouped by month.
-}
sortByLeave : Filters -> Bool
sortByLeave filters =
    filters.sort == "leave" || filters.sort == "leave-desc"


{-| "status=approved&types=ANNUAL,EDU&review=1", leaving out what is as it opens.
-}
toQuery : Bool -> Bool -> Filters -> String
toQuery decides review filters =
    let
        default =
            defaults decides

        param key value isDefaultValue =
            if isDefaultValue then
                Nothing

            else
                Just (key ++ "=" ++ Url.percentEncode value)
    in
    [ param "status" filters.status (filters.status == default.status)
    , param "start" filters.start (filters.start == "")
    , param "end" filters.end (filters.end == "")
    , param "years" (String.join "," (List.map String.fromInt filters.years)) (List.isEmpty filters.years)
    , param "types" (String.join "," filters.types) (List.isEmpty filters.types)
    , param "registrar" (Maybe.map String.fromInt filters.registrar |> Maybe.withDefault "") (filters.registrar == Nothing)
    , param "sort" filters.sort (filters.sort == default.sort)
    , param "review" "1" (not review)
    ]
        |> List.filterMap identity
        |> String.join "&"


{-| The filters in an address's query ("?status=approved&…"), and whether it opens in approval mode. What it
doesn't give, or gives wrongly, is as the page opens.
-}
fromQuery : Bool -> String -> ( Filters, Bool )
fromQuery decides query =
    let
        params =
            query
                |> (\q ->
                        if String.startsWith "?" q then
                            String.dropLeft 1 q

                        else
                            q
                   )
                |> String.split "&"
                |> List.filterMap
                    (\pair ->
                        case String.split "=" pair of
                            [ key, value ] ->
                                Just ( key, Url.percentDecode value |> Maybe.withDefault "" )

                            _ ->
                                Nothing
                    )
                |> Dict.fromList

        get key =
            Dict.get key params |> Maybe.withDefault ""

        default =
            defaults decides

        list =
            String.split "," >> List.filter (not << String.isEmpty)

        oneOf options fallback value =
            if List.member value options then
                value

            else
                fallback

        isoDate value =
            -- "2026-10-10"
            if String.length value == 10 && String.all (\c -> Char.isDigit c || c == '-') value then
                value

            else
                ""
    in
    ( { status = get "status" |> oneOf [ "mine", "waiting", "approved", "declined", "cancelled", "any" ] default.status
      , start = isoDate (get "start")
      , end = isoDate (get "end")
      , years = get "years" |> list |> List.filterMap String.toInt
      , types = get "types" |> list
      , registrar = String.toInt (get "registrar")
      , sort = get "sort" |> oneOf (List.map Tuple.first sorts) default.sort
      }
    , get "review" == "1"
    )
