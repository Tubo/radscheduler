module LeaveRequests exposing (main)

{-| Leave requests waiting for a decision, each beside the roster it affects: the registrar's own days around
it, how many others are on leave, the cover the leave would lose, and the rule breaks it would cause. The chief
registrar and the Director of Training each decide a whole request at once, or day by day.

The requests come from /api/editor/leave-requests, through the client generated from the API's OpenAPI
schema. Decisions save at once with the same endpoint the roster editor uses, and a request-wide decision can
be undone for a few seconds.

Keys: j and k move between requests, a and d approve or decline the one in focus, and the arrow keys move
around a request's roster, which is a single stop for Tab.

-}

import Browser
import Browser.Dom as Dom
import Browser.Events
import Choice exposing (Choice, choiceDecoder, choiceFor)
import Date exposing (Date)
import Dict exposing (Dict)
import Html exposing (..)
import Html.Attributes exposing (..)
import Html.Events exposing (on, onClick, preventDefaultOn)
import Json.Decode as Decode exposing (Decoder)
import Leave exposing (LeaveState(..), leaveChipClass, leaveChipContent, leaveState, leaveStateName, leaveStateSentence, portionLabel)
import OpenApi.Common exposing (Nullable(..))
import Process
import Radscheduler.Api as Api
import Radscheduler.Types as T
import Set exposing (Set)
import Task
import Time


main : Program Decode.Value Model Msg
main =
    Browser.element
        { init = init
        , update = update
        , view = view
        , subscriptions = \_ -> Browser.Events.onKeyDown shortcutDecoder
        }



-- MODEL


type alias Flags =
    { csrfToken : String
    , editorUrl : String
    , shiftTypes : List Choice
    , leaveTypes : List Choice

    -- The decisions this user may make: "reg" (chief registrar) and "dot" (Director of Training).
    , leaveApprovers : List String
    }


type Tab
    = WaitingOnMe
    | AllWaiting
    | Decided


type Remote
    = Loading
    | Failed String
    | Loaded T.LeaveRequestsOut


{-| A decision on some days of one request, by one approver: approve, decline, or back to waiting.
-}
type alias Change =
    { key : Int
    , approver : String
    , leaves : List T.LeaveOut
    , decision : Maybe Bool
    }


{-| The last request-wide decision, which can be undone for a few seconds: the days as they were before it.
-}
type alias Toast =
    { id : Int
    , message : String
    , key : Int
    , approver : String
    , before : List T.LeaveOut
    }


type alias Model =
    { flags : Flags
    , tab : Tab
    , data : Remote

    -- Whether the data loaded holds decided requests, or those waiting.
    , decided : Bool

    -- Numbers each load, so a slow answer to an earlier tab can't replace a later one.
    , asked : Int

    -- The requests listed, by their first day's id, fixed when the list loads: a request decided here stays
    -- in view, showing its new state, until the list is loaded again.
    , shown : List Int
    , saving : Set Int

    -- A save that failed, by request: its changes are put back and the reason shown there.
    , failed : Dict Int String
    , error : Maybe String
    , toast : Maybe Toast
    , toasts : Int

    -- Decided requests opened for a change.
    , changing : Set Int

    -- Requests whose roster is shown, for the Director of Training, who sees a verdict first.
    , expanded : Set Int

    -- The day whose names are shown under a request: the request's key and the day (Rata Die).
    , openDay : Maybe ( Int, Int )

    -- The control in each request's roster that Tab stops at, and the request that last had focus.
    , gridFocus : Dict Int Spot
    , current : Maybe Int

    -- Long rosters scrolled to their end, which lose the fade that says there is more.
    , scrolledEnd : Set Int
    , zone : Time.Zone
    }


type alias ApiError =
    OpenApi.Common.Error Never String


flagsDecoder : Decoder Flags
flagsDecoder =
    Decode.map5 Flags
        (Decode.field "csrfToken" Decode.string)
        (Decode.field "editorUrl" Decode.string)
        (Decode.field "shiftTypes" (Decode.list choiceDecoder))
        (Decode.field "leaveTypes" (Decode.list choiceDecoder))
        (Decode.field "leaveApprovers" (Decode.list Decode.string))


emptyModel : Flags -> Model
emptyModel flags =
    { flags = flags
    , tab =
        if primaryApprover flags == Nothing then
            AllWaiting

        else
            WaitingOnMe
    , data = Loading
    , decided = False
    , asked = 0
    , shown = []
    , saving = Set.empty
    , failed = Dict.empty
    , error = Nothing
    , toast = Nothing
    , toasts = 0
    , changing = Set.empty
    , expanded = Set.empty
    , openDay = Nothing
    , gridFocus = Dict.empty
    , current = Nothing
    , scrolledEnd = Set.empty
    , zone = Time.utc
    }


init : Decode.Value -> ( Model, Cmd Msg )
init value =
    case Decode.decodeValue flagsDecoder value of
        Ok flags ->
            let
                ( loading, cmd ) =
                    load False (emptyModel flags)
            in
            ( loading, Cmd.batch [ cmd, Task.perform GotZone Time.here ] )

        Err err ->
            let
                model =
                    emptyModel { csrfToken = "", editorUrl = "", shiftTypes = [], leaveTypes = [], leaveApprovers = [] }
            in
            ( { model | data = Failed ("The page didn't start: " ++ Decode.errorToString err) }, Cmd.none )


{-| The decision a user makes first: the chief registrar's own, or the Director of Training's.
-}
primaryApprover : Flags -> Maybe String
primaryApprover flags =
    if List.member "reg" flags.leaveApprovers then
        Just "reg"

    else if List.member "dot" flags.leaveApprovers then
        Just "dot"

    else
        Nothing


{-| The Director of Training sees each request's verdict first, and its roster when they ask.
-}
verdictFirst : Flags -> Bool
verdictFirst flags =
    primaryApprover flags == Just "dot"


load : Bool -> Model -> ( Model, Cmd Msg )
load decided model =
    let
        asked =
            model.asked + 1
    in
    ( { model | data = Loading, decided = decided, asked = asked, openDay = Nothing, failed = Dict.empty }
    , Api.getLeaveRequests
        { authorization = { x_csrftoken = model.flags.csrfToken }
        , toMsg = Got asked
        , params = { decided = Just decided }
        }
    )



-- UPDATE


type Msg
    = GotZone Time.Zone
    | ShowTab Tab
    | Reload
    | Got Int (Result ApiError T.LeaveRequestsOut)
    | Decide Bool Change
    | Saved Change (List T.LeaveOut) (Result ApiError (List T.LeaveOut))
    | Undo
    | DismissToast Int
    | StartChange Int
    | ToggleRoster Int
    | ToggleDay Int Int
    | FocusSpot Int Spot
    | MoveSpot Int Spot
    | EnterRequest Int
    | Shortcut String
    | StripScrolled Int Bool
    | NoOp


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        GotZone zone ->
            ( { model | zone = zone }, Cmd.none )

        ShowTab tab ->
            let
                switched =
                    { model | tab = tab, openDay = Nothing, current = Nothing }
            in
            if (tab == Decided) /= model.decided then
                load (tab == Decided) switched

            else
                ( { switched | shown = shownFor switched }, Cmd.none )

        Reload ->
            load model.decided { model | error = Nothing }

        Got asked result ->
            if asked /= model.asked then
                ( model, Cmd.none )

            else
                case result of
                    Ok data ->
                        let
                            loaded =
                                { model | data = Loaded data }
                        in
                        ( { loaded | shown = shownFor loaded }, Cmd.none )

                    Err err ->
                        ( { model | data = Failed ("Couldn't load the leave requests. " ++ errorMessage err) }, Cmd.none )

        Decide undoable change ->
            if List.isEmpty change.leaves then
                ( model, Cmd.none )

            else
                let
                    ( decided, cmd ) =
                        decide change model
                in
                if undoable then
                    let
                        id =
                            model.toasts + 1
                    in
                    ( { decided
                        | toast = Just { id = id, message = changeMessage decided change, key = change.key, approver = change.approver, before = change.leaves }
                        , toasts = id
                      }
                    , Cmd.batch [ cmd, Process.sleep 8000 |> Task.perform (\_ -> DismissToast id) ]
                    )

                else
                    ( decided, cmd )

        Saved change before result ->
            let
                done =
                    { model | saving = Set.diff model.saving (Set.fromList (List.map .id change.leaves)) }
            in
            case result of
                Ok saved ->
                    ( { done | data = replaceLeaves saved done.data }, Cmd.none )

                Err err ->
                    ( { done
                        | data = replaceLeaves before done.data
                        , failed = Dict.insert change.key ("Couldn't save the decision, so it's been put back. " ++ errorMessage err) done.failed
                        , toast = Nothing
                      }
                    , Cmd.none
                    )

        Undo ->
            case model.toast of
                Just toast ->
                    -- Put each day back to the decision it had, grouping the days that had the same one.
                    let
                        groups =
                            toast.before
                                |> List.foldl
                                    (\leave acc ->
                                        let
                                            k =
                                                decisionKey (decisionOf toast.approver leave)
                                        in
                                        Dict.update k (\l -> Just (Maybe.withDefault [] l ++ [ leave ])) acc
                                    )
                                    Dict.empty
                                |> Dict.values

                        ( reverted, cmds ) =
                            List.foldl
                                (\leaves ( m, cs ) ->
                                    case List.head leaves of
                                        Just first ->
                                            let
                                                ( m2, c ) =
                                                    decide { key = toast.key, approver = toast.approver, leaves = leaves, decision = decisionOf toast.approver first } m
                                            in
                                            ( m2, c :: cs )

                                        Nothing ->
                                            ( m, cs )
                                )
                                ( { model | toast = Nothing }, [] )
                                groups
                    in
                    ( reverted, Cmd.batch cmds )

                Nothing ->
                    ( model, Cmd.none )

        DismissToast id ->
            if Maybe.map .id model.toast == Just id then
                ( { model | toast = Nothing }, Cmd.none )

            else
                ( model, Cmd.none )

        StartChange key ->
            ( { model | changing = Set.insert key model.changing }, Cmd.none )

        ToggleRoster key ->
            ( { model | expanded = toggle key model.expanded }, Cmd.none )

        ToggleDay key d ->
            ( { model
                | openDay =
                    if model.openDay == Just ( key, d ) then
                        Nothing

                    else
                        Just ( key, d )
              }
            , Cmd.none
            )

        FocusSpot key spot ->
            ( { model | gridFocus = Dict.insert key spot model.gridFocus, current = Just key }, Cmd.none )

        MoveSpot key spot ->
            ( { model | gridFocus = Dict.insert key spot model.gridFocus }
            , Task.attempt (\_ -> NoOp) (Dom.focus (spotId key spot))
            )

        EnterRequest key ->
            ( { model | current = Just key }, Cmd.none )

        Shortcut key ->
            shortcut key model

        StripScrolled key atEnd ->
            ( { model
                | scrolledEnd =
                    if atEnd then
                        Set.insert key model.scrolledEnd

                    else
                        Set.remove key model.scrolledEnd
              }
            , Cmd.none
            )

        NoOp ->
            ( model, Cmd.none )


{-| Record a decision at once and send it; the days as they were come back if it fails.
-}
decide : Change -> Model -> ( Model, Cmd Msg )
decide change model =
    let
        ids =
            List.map .id change.leaves

        value =
            case change.decision of
                Just b ->
                    Present b

                Nothing ->
                    Null

        apply leave =
            if List.member leave.id ids then
                if change.approver == "reg" then
                    { leave | reg_approved = value }

                else
                    { leave | dot_approved = value }

            else
                leave
    in
    ( { model
        | data = mapLeaves apply model.data
        , saving = Set.union model.saving (Set.fromList ids)
        , failed = Dict.remove change.key model.failed
      }
    , Api.changeLeaves
        { authorization = { x_csrftoken = model.flags.csrfToken }
        , toMsg = Saved change change.leaves
        , body =
            { ids = ids
            , reg_approved = when (change.approver == "reg") value
            , dot_approved = when (change.approver == "dot") value
            , microster = Nothing
            , cancelled = Nothing
            }
        }
    )


{-| "Approved 15 days of Junaid Burney's annual leave as chief registrar."
-}
changeMessage : Model -> Change -> String
changeMessage model change =
    let
        verb =
            case change.decision of
                Just True ->
                    "Approved"

                Just False ->
                    "Declined"

                Nothing ->
                    "Reset"

        whose =
            requestFor model change.key
                |> Maybe.map (\( looks, request ) -> registrarName looks request.registrar ++ "'s " ++ String.toLower (requestTypeName model request))
                |> Maybe.withDefault "the leave"
    in
    verb ++ " " ++ plural (List.length change.leaves) "day" "days" ++ " of " ++ whose ++ " as " ++ approverName change.approver ++ "."


{-| j and k move between requests; a and d approve or decline the one in focus.
-}
shortcut : String -> Model -> ( Model, Cmd Msg )
shortcut key model =
    let
        keys =
            listedKeys model

        index =
            model.current |> Maybe.andThen (\k -> indexOf k keys)

        go i =
            case List.head (List.drop i keys) of
                Just k ->
                    ( { model | current = Just k }, Task.attempt (\_ -> NoOp) (Dom.focus (requestId k)) )

                Nothing ->
                    ( model, Cmd.none )

        decideCurrent decision =
            case ( model.current |> Maybe.andThen (requestFor model), primaryApprover model.flags ) of
                ( Just ( _, request ), Just approver ) ->
                    if editable model (requestKey request) then
                        update (Decide True { key = requestKey request, approver = approver, leaves = waitingFor approver request, decision = Just decision }) model

                    else
                        ( model, Cmd.none )

                _ ->
                    ( model, Cmd.none )
    in
    case key of
        "j" ->
            go (Maybe.map ((+) 1) index |> Maybe.withDefault 0)

        "k" ->
            go (Maybe.map (\i -> Basics.max 0 (i - 1)) index |> Maybe.withDefault 0)

        "a" ->
            decideCurrent True

        "d" ->
            decideCurrent False

        _ ->
            ( model, Cmd.none )


{-| Single-letter keys, unless typing in a field or holding a modifier.
-}
shortcutDecoder : Decoder Msg
shortcutDecoder =
    Decode.map5
        (\key ctrl meta alt tag ->
            if ctrl || meta || alt || List.member tag [ "INPUT", "TEXTAREA", "SELECT" ] || not (List.member key [ "j", "k", "a", "d" ]) then
                NoOp

            else
                Shortcut key
        )
        (Decode.field "key" Decode.string)
        (Decode.field "ctrlKey" Decode.bool)
        (Decode.field "metaKey" Decode.bool)
        (Decode.field "altKey" Decode.bool)
        (Decode.oneOf [ Decode.at [ "target", "tagName" ] Decode.string, Decode.succeed "" ])


when : Bool -> a -> Maybe a
when condition value =
    if condition then
        Just value

    else
        Nothing


toggle : comparable -> Set comparable -> Set comparable
toggle item set =
    if Set.member item set then
        Set.remove item set

    else
        Set.insert item set


decisionKey : Maybe Bool -> Int
decisionKey decision =
    case decision of
        Just True ->
            1

        Just False ->
            0

        Nothing ->
            -1


{-| The requests the tab lists, by key, in the server's order.
-}
shownFor : Model -> List Int
shownFor model =
    case model.data of
        Loaded data ->
            data.requests
                |> List.filter
                    (\request ->
                        case ( model.tab, primaryApprover model.flags ) of
                            ( WaitingOnMe, Just approver ) ->
                                not (List.isEmpty (waitingFor approver request))

                            _ ->
                                True
                    )
                |> List.map requestKey

        _ ->
            []


{-| The keys in the order they are drawn, groups included.
-}
listedKeys : Model -> List Int
listedKeys model =
    case model.data of
        Loaded data ->
            groupsFor model data |> List.concatMap (Tuple.second >> List.map requestKey)

        _ ->
            []


requestFor : Model -> Int -> Maybe ( Lookups, T.LeaveRequestOut )
requestFor model key =
    case model.data of
        Loaded data ->
            data.requests |> List.filter (\r -> requestKey r == key) |> List.head |> Maybe.map (Tuple.pair (lookups data))

        _ ->
            Nothing


mapLeaves : (T.LeaveOut -> T.LeaveOut) -> Remote -> Remote
mapLeaves f remote =
    case remote of
        Loaded data ->
            Loaded { data | requests = List.map (\r -> { r | leaves = List.map f r.leaves }) data.requests }

        _ ->
            remote


replaceLeaves : List T.LeaveOut -> Remote -> Remote
replaceLeaves leaves =
    let
        byId =
            Dict.fromList (List.map (\l -> ( l.id, l )) leaves)
    in
    mapLeaves (\l -> Dict.get l.id byId |> Maybe.withDefault l)


errorMessage : ApiError -> String
errorMessage error =
    case error of
        OpenApi.Common.BadUrl url ->
            "Bad URL: " ++ url

        OpenApi.Common.Timeout ->
            "The server took too long to respond."

        OpenApi.Common.NetworkError ->
            "Couldn't reach the server. Check your connection."

        OpenApi.Common.KnownBadStatus _ body ->
            never body

        OpenApi.Common.UnknownBadStatus metadata _ ->
            statusMessage metadata.statusCode

        OpenApi.Common.BadErrorBody metadata _ ->
            statusMessage metadata.statusCode

        OpenApi.Common.BadBody _ _ ->
            "The server sent a response the page didn't understand. Reload the page."


statusMessage : Int -> String
statusMessage status =
    case status of
        401 ->
            "You've been signed out. Reload the page to sign in again."

        403 ->
            "Your account can't make this decision; ask the chief registrar."

        _ ->
            "Something went wrong on the server (" ++ String.fromInt status ++ "). Try again."



-- REQUESTS


requestKey : T.LeaveRequestOut -> Int
requestKey request =
    List.head request.leaves |> Maybe.map .id |> Maybe.withDefault 0


decisionOf : String -> T.LeaveOut -> Maybe Bool
decisionOf approver leave =
    nullable
        (if approver == "reg" then
            leave.reg_approved

         else
            leave.dot_approved
        )


approverName : String -> String
approverName approver =
    if approver == "reg" then
        "chief registrar"

    else
        "Director of Training"


{-| Leave that takes the registrar off the roster: not cancelled or declined.
-}
isActive : T.LeaveOut -> Bool
isActive leave =
    case leaveState leave of
        Cancelled ->
            False

        Declined ->
            False

        _ ->
            True


{-| The days still waiting for an approver: not declined by either, and not yet decided by them.
-}
waitingFor : String -> T.LeaveRequestOut -> List T.LeaveOut
waitingFor approver request =
    List.filter (\l -> isActive l && decisionOf approver l == Nothing) request.leaves


{-| Whether the user can change a request here: anything waiting, or a decided one they opened to change.
-}
editable : Model -> Int -> Bool
editable model key =
    model.tab /= Decided || Set.member key model.changing


{-| "Annual leave", "Lieu day"
-}
requestTypeName : { a | flags : Flags } -> T.LeaveRequestOut -> String
requestTypeName model request =
    case List.head request.leaves of
        Just leave ->
            leaveName (choiceFor model.flags.leaveTypes (T.leaveTypeToString leave.type_))

        Nothing ->
            "Leave"


leaveName : Choice -> String
leaveName choice =
    if String.contains "day" (String.toLower choice.label) || String.contains "leave" (String.toLower choice.label) then
        choice.label

    else
        choice.label ++ " leave"


shiftName : { a | flags : Flags } -> T.ShiftType -> String
shiftName model shiftType =
    (choiceFor model.flags.shiftTypes (T.shiftTypeToString shiftType)).label


{-| A day of leave counts as one, or a half for a morning or an afternoon.
-}
weight : String -> Float
weight portion =
    if portion == "ALL" then
        1

    else
        0.5


{-| "2½"
-}
formatDays : Float -> String
formatDays n =
    let
        whole =
            floor n

        half =
            n - toFloat whole >= 0.5
    in
    case ( whole, half ) of
        ( 0, True ) ->
            "½"

        ( _, True ) ->
            String.fromInt whole ++ "½"

        _ ->
            String.fromInt whole


daysLabel : Float -> String
daysLabel n =
    formatDays n
        ++ (if n > 1 then
                " days"

            else
                " day"
           )


{-| Everyone on leave on a day, this request's active days included, counted in halves.
-}
awayOn : T.LeaveRequestOut -> Int -> Float
awayOn request d =
    (request.away |> List.filter (\a -> Date.toRataDie a.date == d) |> List.map (.portion >> weight) |> List.sum)
        + (request.leaves |> List.filter (\l -> Date.toRataDie l.date == d && isActive l) |> List.map (.portion >> weight) |> List.sum)


dayInfo : T.LeaveRequestOut -> Int -> Maybe T.RequestDayOut
dayInfo request d =
    request.days |> List.filter (\i -> Date.toRataDie i.date == d) |> List.head


{-| 0 for nobody on leave, then 1 to 4 for under 10%, 10–20%, 20–30% and 30% or more of the roster.
-}
heatStep : Float -> Int -> Int
heatStep count rostered =
    let
        share =
            count / toFloat (Basics.max 1 rostered)
    in
    if count == 0 then
        0

    else if share < 0.1 then
        1

    else if share < 0.2 then
        2

    else if share < 0.3 then
        3

    else
        4



-- GRID FOCUS


{-| A control in a request's roster: its row (0 chief registrar, 1 Director of Training, 2 on leave) and column
(two per day: approve, then decline; the day's count takes the first).
-}
type alias Spot =
    ( Int, Int )


spotId : Int -> Spot -> String
spotId key ( row, col ) =
    "spot-" ++ String.fromInt key ++ "-" ++ String.fromInt row ++ "-" ++ String.fromInt col


requestId : Int -> String
requestId key =
    "request-" ++ String.fromInt key


{-| The controls a request's roster offers this user, by row, in column order.
-}
spots : Model -> T.LeaveRequestOut -> List Spot
spots model request =
    let
        key =
            requestKey request

        asked =
            List.map (\l -> Date.toRataDie l.date) request.leaves

        decisionSpots row approver =
            if List.member approver model.flags.leaveApprovers && editable model key then
                request.dates
                    |> List.indexedMap Tuple.pair
                    |> List.filter (\( _, date ) -> List.member (Date.toRataDie date) asked)
                    |> List.concatMap (\( i, _ ) -> [ ( row, i * 2 ), ( row, i * 2 + 1 ) ])

            else
                []
    in
    decisionSpots 0 "reg" ++ decisionSpots 1 "dot" ++ List.indexedMap (\i _ -> ( 2, i * 2 )) request.dates


{-| The control Tab stops at in a request's roster: the last one used, or the first.
-}
tabStop : Model -> T.LeaveRequestOut -> Maybe Spot
tabStop model request =
    let
        all =
            spots model request
    in
    case Dict.get (requestKey request) model.gridFocus of
        Just spot ->
            if List.member spot all then
                Just spot

            else
                List.head all

        Nothing ->
            List.head all


{-| Arrow keys within a roster: along a row, or to the nearest control in the row above or below.
-}
arrowDecoder : Model -> T.LeaveRequestOut -> Spot -> Decoder ( Msg, Bool )
arrowDecoder model request ( row, col ) =
    let
        all =
            spots model request

        inRow r =
            List.filter (\( r2, _ ) -> r2 == r) all

        rows =
            all |> List.map Tuple.first |> Set.fromList |> Set.toList

        nearest r =
            inRow r |> List.sortBy (\( _, c ) -> abs (c - col)) |> List.head

        along step =
            let
                candidates =
                    inRow row |> List.filter (\( _, c ) -> step * (c - col) > 0) |> List.sortBy (\( _, c ) -> step * c)
            in
            List.head candidates

        across step =
            rows |> List.filter (\r -> step * (r - row) > 0) |> List.sortBy (\r -> step * r) |> List.head |> Maybe.andThen nearest

        move target =
            case target of
                Just spot ->
                    Decode.succeed ( MoveSpot (requestKey request) spot, True )

                Nothing ->
                    Decode.succeed ( NoOp, True )
    in
    Decode.field "key" Decode.string
        |> Decode.andThen
            (\key ->
                case key of
                    "ArrowRight" ->
                        move (along 1)

                    "ArrowLeft" ->
                        move (along -1)

                    "ArrowDown" ->
                        move (across 1)

                    "ArrowUp" ->
                        move (across -1)

                    "Home" ->
                        move (List.head (inRow row))

                    "End" ->
                        move (List.head (List.reverse (inRow row)))

                    _ ->
                        Decode.fail "not an arrow"
            )


{-| A roster control's focus behaviour: one stop for Tab, arrow keys inside.
-}
spotAttributes : Model -> T.LeaveRequestOut -> Spot -> List (Attribute Msg)
spotAttributes model request spot =
    let
        key =
            requestKey request
    in
    [ id (spotId key spot)
    , tabindex
        (if tabStop model request == Just spot then
            0

         else
            -1
        )
    , on "focus" (Decode.succeed (FocusSpot key spot))
    , preventDefaultOn "keydown" (arrowDecoder model request spot)
    ]



-- VIEW


view : Model -> Html Msg
view model =
    div [ class "leave-requests" ]
        [ header [ class "lr-head" ]
            [ h1 [] [ text "Leave requests" ]
            , p [ class "lr-role" ] [ text (roleLine model.flags) ]
            , viewHelp model
            ]
        , div [ class "lr-bar" ] [ viewTabs model, viewScale ]
        , case model.error of
            Just message ->
                div [ class "re-note is-error lr-alert", attribute "role" "alert" ] [ text message ]

            Nothing ->
                text ""
        , viewBody model
        , div [ class "re-toasts", attribute "aria-live" "polite" ] [ viewToast model.toast ]
        ]


roleLine : Flags -> String
roleLine flags =
    case ( List.member "reg" flags.leaveApprovers, List.member "dot" flags.leaveApprovers ) of
        ( True, True ) ->
            "You decide as chief registrar, and can record the Director of Training's decisions for them."

        ( True, False ) ->
            "You decide as chief registrar."

        ( False, True ) ->
            "You decide as Director of Training. The chief registrar decides first; leave needs both approvals."

        ( False, False ) ->
            "You can see leave requests; the chief registrar and the Director of Training decide them."


viewHelp : Model -> Html Msg
viewHelp model =
    let
        -- Only the short forms that aren't simply the first word of the name.
        needsSaying c =
            Just (String.toLower c.short) /= List.head (String.words (String.toLower c.label))

        abbreviations =
            (model.flags.leaveTypes |> List.filter needsSaying |> List.map (\c -> c.short ++ " " ++ String.toLower (leaveName c)))
                ++ (model.flags.shiftTypes |> List.filter needsSaying |> List.map (\c -> c.short ++ " " ++ String.toLower c.label))
                ++ [ "RDO rostered day off" ]
    in
    details [ class "lr-help" ]
        [ summary [] [ text "How this page works" ]
        , ul []
            [ li [] [ text "Leave needs two approvals, the chief registrar's and the Director of Training's; either can decline it." ]
            , li [] [ text "Approve or Decline a whole request, or one day with ✓ and ✗ in its column. The request buttons only change days still waiting for you, and can be undone for a few seconds." ]
            , li [] [ text "Under each request: their roster around it, how many are on leave each day (this request included, shaded by their share of the roster; click for names), the cover the leave would lose, and the rule breaks it would cause." ]
            , li [] [ text ("Short forms: " ++ String.join " · " abbreviations ++ ".") ]
            , li [] [ text "Keys: j and k move between requests, a and d approve or decline the one in focus, and the arrow keys move around its roster." ]
            ]
        ]


viewTabs : Model -> Html Msg
viewTabs model =
    let
        count tab =
            case ( model.data, model.decided ) of
                ( Loaded data, False ) ->
                    case ( tab, primaryApprover model.flags ) of
                        ( WaitingOnMe, Just approver ) ->
                            Just (List.length (List.filter (waitingFor approver >> List.isEmpty >> not) data.requests))

                        ( AllWaiting, _ ) ->
                            Just (List.length (List.filter (\r -> not (List.isEmpty (waitingFor "reg" r ++ waitingFor "dot" r))) data.requests))

                        _ ->
                            Nothing

                _ ->
                    Nothing

        tabButton tab label =
            button
                [ type_ "button"
                , class "lr-tab"
                , classList [ ( "is-on", model.tab == tab ) ]
                , attribute "aria-pressed" (boolString (model.tab == tab))
                , onClick (ShowTab tab)
                ]
                (text label
                    :: (case count tab of
                            Just n ->
                                [ span [ class "lr-tabcount" ] [ text (String.fromInt n) ] ]

                            Nothing ->
                                []
                       )
                )
    in
    div [ class "lr-tabs", attribute "role" "group", attribute "aria-label" "Which requests" ]
        ((if primaryApprover model.flags /= Nothing then
            [ tabButton WaitingOnMe "Waiting on you" ]

          else
            []
         )
            ++ [ tabButton AllWaiting "All waiting"
               , tabButton Decided "Decided lately"
               ]
        )


{-| The colour scale of the "On leave" row, as a key.
-}
viewScale : Html Msg
viewScale =
    div [ class "lr-scale" ]
        [ span [ class "lr-scale-title" ] [ text "Share of the roster on leave" ]
        , ul [ class "lr-scale-steps" ]
            (List.map
                (\( step, label ) ->
                    li [] [ span [ class ("lr-swatch is-" ++ String.fromInt step), attribute "aria-hidden" "true" ] [], text label ]
                )
                [ ( 1, "under 10%" ), ( 2, "10–20%" ), ( 3, "20–30%" ), ( 4, "30% or more" ) ]
            )
        ]


viewToast : Maybe Toast -> Html Msg
viewToast toast =
    case toast of
        Just t ->
            div [ class "re-toast" ]
                [ span [ class "re-toast-text" ] [ text t.message ]
                , button [ type_ "button", class "re-btn re-btn--on-dark", onClick Undo ]
                    [ i [ class "bi bi-arrow-counterclockwise", attribute "aria-hidden" "true" ] [], text "Undo" ]
                , button [ type_ "button", class "btn-close btn-close-white", attribute "aria-label" "Dismiss", onClick (DismissToast t.id) ] []
                ]

        Nothing ->
            text ""


viewBody : Model -> Html Msg
viewBody model =
    case model.data of
        Loading ->
            p [ class "lr-loading", attribute "role" "status" ]
                [ span [ class "spinner-border spinner-border-sm", attribute "aria-hidden" "true" ] []
                , text "Loading leave requests"
                ]

        Failed message ->
            div [ class "re-note is-error lr-alert", attribute "role" "alert" ]
                [ text message
                , text " "
                , button [ type_ "button", class "re-btn", onClick Reload ] [ text "Try again" ]
                ]

        Loaded data ->
            let
                groups =
                    groupsFor model data
            in
            if List.all (Tuple.second >> List.isEmpty) groups then
                viewEmpty model

            else
                div [ class "lr-list" ]
                    (List.filterMap
                        (\( heading, requests ) ->
                            if List.isEmpty requests then
                                Nothing

                            else
                                Just
                                    (section [ class "lr-group", attribute "aria-label" heading ]
                                        (h2 [ class "lr-group-title" ]
                                            [ text heading
                                            , span [ class "lr-group-count" ] [ text (String.fromInt (List.length requests)) ]
                                            ]
                                            :: List.map (viewRequest model (lookups data)) requests
                                        )
                                    )
                        )
                        groups
                    )


{-| The requests listed, in groups with a heading each: by month of their first day, or for the Director of
Training waiting on them, those the chief registrar has approved first.
-}
groupsFor : Model -> T.LeaveRequestsOut -> List ( String, List T.LeaveRequestOut )
groupsFor model data =
    let
        byKey =
            Dict.fromList (List.map (\r -> ( requestKey r, r )) data.requests)

        requests =
            List.filterMap (\key -> Dict.get key byKey) model.shown

        firstDate r =
            List.head r.leaves |> Maybe.map .date
    in
    case ( model.tab, verdictFirst model.flags ) of
        ( Decided, _ ) ->
            [ ( "Decided in the last 30 days", requests ) ]

        ( WaitingOnMe, True ) ->
            let
                ( approved, unseen ) =
                    List.partition (\r -> List.all (\l -> not (isActive l) || decisionOf "reg" l == Just True) r.leaves) requests
            in
            [ ( "Approved by the chief registrar", approved ), ( "Not yet decided by the chief registrar", unseen ) ]

        _ ->
            requests
                |> List.foldr
                    (\r acc ->
                        let
                            month =
                                firstDate r |> Maybe.map (Date.format "MMMM y") |> Maybe.withDefault ""
                        in
                        case acc of
                            ( m, rs ) :: rest ->
                                if m == month then
                                    ( m, r :: rs ) :: rest

                                else
                                    ( month, [ r ] ) :: acc

                            [] ->
                                [ ( month, [ r ] ) ]
                    )
                    []


viewEmpty : Model -> Html Msg
viewEmpty model =
    let
        ( message, next ) =
            case model.tab of
                WaitingOnMe ->
                    ( "Nothing is waiting on you.", Just ( AllWaiting, "See everything waiting" ) )

                AllWaiting ->
                    ( "No leave is waiting for a decision.", Just ( Decided, "See recent decisions" ) )

                Decided ->
                    ( "No leave has been decided in the last 30 days.", Nothing )
    in
    div [ class "lr-empty" ]
        [ i [ class "bi bi-check2-circle", attribute "aria-hidden" "true" ] []
        , p [] [ text message ]
        , case next of
            Just ( tab, label ) ->
                button [ type_ "button", class "re-btn re-btn--quiet", onClick (ShowTab tab) ] [ text label ]

            Nothing ->
                text ""
        ]


type alias Lookups =
    { registrars : Dict Int T.RegistrarOut
    , holidays : Dict Int String
    }


lookups : T.LeaveRequestsOut -> Lookups
lookups data =
    { registrars = Dict.fromList (List.map (\r -> ( r.id, r )) data.registrars)
    , holidays = Dict.fromList (List.map (\h -> ( Date.toRataDie h.date, h.name )) data.holidays)
    }


registrarName : Lookups -> Int -> String
registrarName looks id =
    Dict.get id looks.registrars |> Maybe.map .name |> Maybe.withDefault "A registrar"


viewRequest : Model -> Lookups -> T.LeaveRequestOut -> Html Msg
viewRequest model looks request =
    let
        key =
            requestKey request

        titleId =
            requestId key ++ "-title"

        registrar =
            Dict.get request.registrar looks.registrars

        first =
            List.head request.leaves

        days =
            List.map (\l -> weight l.portion) request.leaves |> List.sum

        comments =
            request.leaves |> List.map (.comment >> String.trim) |> List.filter (not << String.isEmpty) |> unique

        showRoster =
            not (verdictFirst model.flags) || Set.member key model.expanded

        stripId =
            requestId key ++ "-roster"
    in
    article
        [ class "lr-request"
        , classList [ ( "has-roster", showRoster ) ]
        , id (requestId key)
        , tabindex -1
        , attribute "aria-labelledby" titleId
        , on "focusin" (Decode.succeed (EnterRequest key))
        ]
        [ div [ class "lr-side" ]
            [ h3 [ class "lr-name", id titleId ]
                [ text (Maybe.map .name registrar |> Maybe.withDefault "A registrar")
                , case registrar |> Maybe.andThen (.year >> nullable) of
                    Just year ->
                        span [ class "lr-year" ] [ text (" Year " ++ String.fromInt year) ]

                    Nothing ->
                        text ""
                ]
            , p [ class "lr-what" ]
                [ strong [] [ text (requestTypeName model request) ]
                , text
                    (" · "
                        ++ spanLabel (List.map .date request.leaves)
                        ++ (case first of
                                Just l ->
                                    if l.portion == "ALL" then
                                        ""

                                    else
                                        portionLabel l

                                Nothing ->
                                    ""
                           )
                        ++ " · "
                        ++ daysLabel days
                    )
                ]
            , p [ class "lr-meta" ] [ text (askedLine model.zone request) ]
            , if List.isEmpty comments then
                text ""

              else
                div [ class "lr-comment" ]
                    [ i [ class "bi bi-chat-left-quote", attribute "aria-hidden" "true" ] []
                    , div [] (List.map (\c -> p [] [ text c ]) comments)
                    ]
            , viewVerdict model looks request
            , viewDecide model looks request
            , case Dict.get key model.failed of
                Just message ->
                    div [ class "re-note is-error", attribute "role" "alert" ] [ text message ]

                Nothing ->
                    text ""
            , div [ class "lr-links" ]
                ((if verdictFirst model.flags then
                    [ button
                        [ type_ "button"
                        , class "re-btn re-btn--quiet"
                        , attribute "aria-expanded" (boolString showRoster)
                        , attribute "aria-controls" stripId
                        , onClick (ToggleRoster key)
                        ]
                        [ i
                            [ class
                                (if showRoster then
                                    "bi bi-chevron-up"

                                 else
                                    "bi bi-chevron-down"
                                )
                            , attribute "aria-hidden" "true"
                            ]
                            []
                        , text
                            (if showRoster then
                                "Hide their roster"

                             else
                                "Show their roster"
                            )
                        ]
                    ]

                  else
                    []
                 )
                    ++ [ a [ class "re-btn re-btn--quiet", href (editorLink model request) ]
                            [ i [ class "bi bi-calendar-week", attribute "aria-hidden" "true" ] [], text "Open in the roster editor" ]
                       ]
                )
            , viewBreaks request
            ]
        , if showRoster then
            div [ class "lr-main", id stripId ]
                [ div
                    [ class "lr-strip"
                    , classList [ ( "is-faded", List.length request.dates > 9 && not (Set.member key model.scrolledEnd) ) ]
                    , on "scroll" (scrolledDecoder key)
                    ]
                    [ viewGrid model looks request ]
                , viewDayNames model looks request
                ]

          else
            text ""
        ]


scrolledDecoder : Int -> Decoder Msg
scrolledDecoder key =
    Decode.map3 (\left width client -> StripScrolled key (left + client >= width - 4))
        (Decode.at [ "target", "scrollLeft" ] Decode.float)
        (Decode.at [ "target", "scrollWidth" ] Decode.float)
        (Decode.at [ "target", "clientWidth" ] Decode.float)


editorLink : Model -> T.LeaveRequestOut -> String
editorLink model request =
    case List.head request.leaves of
        Just leave ->
            model.flags.editorUrl ++ Date.toIsoString leave.date ++ "/"

        Nothing ->
            model.flags.editorUrl


{-| "Asked 3 Aug 2026, 178 days ahead"
-}
askedLine : Time.Zone -> T.LeaveRequestOut -> String
askedLine zone request =
    case ( request.leaves |> List.map (.created >> Time.posixToMillis) |> List.minimum, List.head request.leaves ) of
        ( Just millis, Just first ) ->
            let
                asked =
                    Date.fromPosix zone (Time.millisToPosix millis)

                ahead =
                    Date.diff Date.Days asked first.date
            in
            "Asked "
                ++ Date.format "d MMM y" asked
                ++ (if ahead > 0 then
                        ", " ++ plural ahead "day" "days" ++ " ahead"

                    else if ahead == 0 then
                        ", on the day"

                    else
                        ", " ++ plural (negate ahead) "day" "days" ++ " after it began"
                   )

        _ ->
            ""


{-| The answer to "can it be given?" in one line: how many would be away, the cover it loses, and the rule
breaks it causes.
-}
viewVerdict : Model -> Lookups -> T.LeaveRequestOut -> Html Msg
viewVerdict model _ request =
    let
        asked =
            request.leaves |> List.filter isActive |> List.map (\l -> Date.toRataDie l.date) |> unique

        peak =
            asked
                |> List.map (\d -> ( awayOn request d, dayInfo request d |> Maybe.map .registrars |> Maybe.withDefault 0 ))
                |> List.sortBy (\( n, of_ ) -> negate (n / toFloat (Basics.max 1 of_)))
                |> List.head

        rostered =
            List.any (\d -> dayInfo request d |> Maybe.map .rostered |> Maybe.withDefault False) asked

        lost =
            asked
                |> List.concatMap
                    (\d ->
                        dayInfo request d
                            |> Maybe.map .lost
                            |> Maybe.withDefault []
                            |> List.map (\need -> String.join " or " (List.map (shiftName model) need) ++ " on " ++ Date.format "EEE d MMM" (Date.fromRataDie d))
                    )

        away =
            case peak of
                Just ( n, of_ ) ->
                    (if List.length asked > 1 then
                        "Up to "

                     else
                        ""
                    )
                        ++ formatDays n
                        ++ " of "
                        ++ String.fromInt of_
                        ++ " on leave"

                Nothing ->
                    "Nothing left to give"

        cover =
            if not rostered then
                "roster not built yet"

            else
                case lost of
                    [] ->
                        "no cover lost"

                    [ one ] ->
                        one ++ " lost"

                    _ ->
                        "cover lost on " ++ plural (List.length lost) "shift" "shifts"

        breaks =
            case List.length request.violations of
                0 ->
                    "no rule breaks caused"

                n ->
                    plural n "rule break" "rule breaks" ++ " caused"

        concern =
            not (List.isEmpty lost) || not (List.isEmpty request.violations)
    in
    p [ class "lr-verdict", classList [ ( "is-concern", concern ) ] ]
        [ i
            [ class
                (if concern then
                    "bi bi-exclamation-triangle-fill"

                 else
                    "bi bi-check-circle-fill"
                )
            , attribute "aria-hidden" "true"
            ]
            []
        , span [] ([ away, cover, breaks ] |> List.map (\part -> span [ class "lr-verdict-part" ] [ text part ]) |> List.intersperse (text " · "))
        ]


{-| The request's own buttons, for the user's first decision: they only change the days still waiting for
them. Once none are, a summary of what they decided.
-}
viewDecide : Model -> Lookups -> T.LeaveRequestOut -> Html Msg
viewDecide model looks request =
    let
        key =
            requestKey request

        active =
            List.filter (\l -> not l.cancelled) request.leaves

        busy =
            List.any (\l -> Set.member l.id model.saving) request.leaves

        status =
            case unique (List.map leaveStateSentence active) of
                [ one ] ->
                    one

                [] ->
                    "Cancelled."

                _ ->
                    mixedStatus active

        whose =
            registrarName looks request.registrar ++ "'s " ++ String.toLower (requestTypeName model request)
    in
    div [ class "lr-decide" ]
        ((case primaryApprover model.flags of
            Just approver ->
                let
                    waiting =
                        waitingFor approver request

                    -- Some days already decided, declined ones included: say which days the buttons change.
                    some =
                        List.length waiting < List.length active

                    action decision verb icon variant =
                        button
                            [ type_ "button"
                            , class ("re-btn " ++ variant)
                            , disabled busy
                            , attribute "aria-label"
                                (verb
                                    ++ (if some then
                                            " the " ++ plural (List.length waiting) "waiting day" "waiting days" ++ " of "

                                        else
                                            " "
                                       )
                                    ++ whose
                                )
                            , onClick (Decide True { key = key, approver = approver, leaves = waiting, decision = Just decision })
                            ]
                            [ i [ class ("bi " ++ icon), attribute "aria-hidden" "true" ] []
                            , text
                                (verb
                                    ++ (if some then
                                            " " ++ plural (List.length waiting) "waiting day" "waiting days"

                                        else
                                            ""
                                       )
                                )
                            ]
                in
                if not (editable model key) then
                    [ p [ class "lr-mine" ] [ text (mineSummary approver request) ]
                    , button [ type_ "button", class "re-btn", onClick (StartChange key) ]
                        [ i [ class "bi bi-pencil", attribute "aria-hidden" "true" ] [], text "Change decision" ]
                    ]

                else if List.isEmpty waiting then
                    [ p [ class "lr-mine" ]
                        [ text
                            (mineSummary approver request
                                ++ (if verdictFirst model.flags && not (Set.member key model.expanded) then
                                        ""

                                    else
                                        " Change a day with its ✓ and ✗."
                                   )
                            )
                        ]
                    ]

                else
                    [ div [ class "lr-actions" ]
                        [ action True "Approve" "bi-check-lg" "re-btn--primary"
                        , action False "Decline" "bi-x-lg" "re-btn--danger-quiet"
                        ]
                    ]

            Nothing ->
                []
         )
            ++ [ p [ class "lr-status", attribute "aria-live" "polite" ] [ text status ] ]
        )


{-| "You approved all 5 days.", "You approved 4 days and declined 1."
-}
mineSummary : String -> T.LeaveRequestOut -> String
mineSummary approver request =
    let
        count value =
            List.length (List.filter (\l -> not l.cancelled && decisionOf approver l == Just value) request.leaves)

        approved =
            count True

        declined =
            count False

        total =
            List.length (List.filter (not << .cancelled) request.leaves)
    in
    if approved == total && total > 1 then
        "You approved all " ++ String.fromInt total ++ " days."

    else if approved == total then
        "You approved it."

    else if declined == total && total > 1 then
        "You declined all " ++ String.fromInt total ++ " days."

    else if declined == total then
        "You declined it."

    else if declined == 0 && approved > 0 then
        "You approved " ++ plural approved "day" "days" ++ "; the rest were declined by the other approver."

    else if approved == 0 && declined > 0 then
        "You declined " ++ plural declined "day" "days" ++ "; the rest were declined by the other approver."

    else
        "You approved " ++ plural approved "day" "days" ++ " and declined " ++ String.fromInt declined ++ "."


{-| "2 days approved, 1 declined, 14 waiting", for a request decided differently from day to day.
-}
mixedStatus : List T.LeaveOut -> String
mixedStatus leaves =
    let
        count state =
            List.length (List.filter (\l -> leaveState l == state) leaves)

        waiting =
            count Pending + count PartlyApproved
    in
    [ ( count Approved, "approved" ), ( count Declined, "declined" ), ( waiting, "waiting" ) ]
        |> List.filter (\( n, _ ) -> n > 0)
        |> List.indexedMap
            (\index ( n, what ) ->
                if index == 0 then
                    plural n "day" "days" ++ " " ++ what

                else
                    String.fromInt n ++ " " ++ what
            )
        |> String.join ", "


{-| The rule breaks this leave would cause, and, folded away, those already on their roster.
-}
viewBreaks : T.LeaveRequestOut -> Html Msg
viewBreaks request =
    let
        rule v =
            li []
                [ span [ class "re-clause" ] [ text (nullable v.clause |> Maybe.withDefault "Department rule") ]
                , text v.message
                ]
    in
    div [ class "lr-breaks" ]
        [ if List.isEmpty request.violations then
            text ""

          else
            div []
                [ h4 [ class "re-label" ] [ text ("Caused by this leave: " ++ plural (List.length request.violations) "rule break" "rule breaks") ]
                , ul [ class "re-rulelist" ] (List.map rule request.violations)
                ]
        , if List.isEmpty request.existing_violations then
            text ""

          else
            details [ class "lr-existing" ]
                [ summary [ class "re-label" ] [ text (plural (List.length request.existing_violations) "rule break" "rule breaks" ++ " already on their roster") ]
                , ul [ class "re-rulelist" ] (List.map rule request.existing_violations)
                ]
        ]


viewGrid : Model -> Lookups -> T.LeaveRequestOut -> Html Msg
viewGrid model looks request =
    let
        key =
            requestKey request

        asked =
            Dict.fromList (List.map (\l -> ( Date.toRataDie l.date, l )) request.leaves)

        columnClasses date =
            [ ( "is-weekend", isWeekend date )
            , ( "is-holiday", Dict.member (Date.toRataDie date) looks.holidays )
            , ( "is-asked", Dict.member (Date.toRataDie date) asked )
            ]

        dated =
            List.indexedMap Tuple.pair request.dates

        row label cells =
            tr [] (th [ scope "row", class "lr-rowlabel" ] label :: List.map (\( i, date ) -> td [ classList (columnClasses date) ] (cells i date)) dated)

        decisionRow index approver who =
            let
                canChange =
                    List.member approver model.flags.leaveApprovers && editable model key

                waiting =
                    waitingFor approver request
            in
            row
                [ span [ class "lr-rowname" ] [ text who ]
                , if canChange && List.length waiting > 1 then
                    span [ class "lr-rowall" ]
                        [ button
                            [ type_ "button"
                            , class "lr-mini"
                            , attribute "aria-label" ("Approve every waiting day as " ++ who)
                            , title ("Approve every waiting day as " ++ who)
                            , onClick (Decide True { key = key, approver = approver, leaves = waiting, decision = Just True })
                            ]
                            [ i [ class "bi bi-check-lg", attribute "aria-hidden" "true" ] [], text "all" ]
                        , button
                            [ type_ "button"
                            , class "lr-mini"
                            , attribute "aria-label" ("Decline every waiting day as " ++ who)
                            , title ("Decline every waiting day as " ++ who)
                            , onClick (Decide True { key = key, approver = approver, leaves = waiting, decision = Just False })
                            ]
                            [ i [ class "bi bi-x-lg", attribute "aria-hidden" "true" ] [], text "all" ]
                        ]

                  else
                    text ""
                ]
                (\i date ->
                    case Dict.get (Date.toRataDie date) asked of
                        Just leave ->
                            [ viewDecision model request index i approver who canChange leave ]

                        Nothing ->
                            []
                )

        rosters =
            request.days |> List.map .registrars |> unique

        ofRoster =
            case ( List.minimum rosters, List.maximum rosters ) of
                ( Just lo, Just hi ) ->
                    if lo == hi then
                        "of " ++ String.fromInt lo

                    else
                        "of " ++ String.fromInt lo ++ "–" ++ String.fromInt hi

                _ ->
                    ""

        anyRostered =
            List.any .rostered request.days
    in
    table [ class "lr-grid", attribute "aria-label" ("Roster around " ++ registrarName looks request.registrar ++ "'s leave") ]
        [ thead []
            [ tr []
                (th [ class "lr-corner" ] [ span [ class "visually-hidden" ] [ text "Day" ] ]
                    :: List.map
                        (\date ->
                            let
                                holiday =
                                    Dict.get (Date.toRataDie date) looks.holidays
                            in
                            th [ scope "col", classList (columnClasses date) ]
                                [ span [ class "lr-weekday" ] [ text (Date.format "EEE" date) ]
                                , span [ class "lr-daydate" ] [ text (Date.format "d MMM" date) ]
                                , case holiday of
                                    Just name ->
                                        span [ class "lr-holiday" ] [ text name ]

                                    Nothing ->
                                        text ""
                                ]
                        )
                        request.dates
                )
            ]
        , tbody []
            [ row [ text "Their roster" ] (\_ date -> viewOwnDay model request asked date)
            , decisionRow 0 "reg" "Chief registrar"
            , decisionRow 1 "dot" "Director of Training"
            , row [ span [ class "lr-rowname" ] [ text "On leave" ], span [ class "lr-rowsub" ] [ text (ofRoster ++ " on the roster") ] ]
                (\i date -> [ viewAway model request key i date ])
            , if anyRostered then
                row [ text "Cover lost" ] (\_ date -> [ viewCover model (dayInfo request (Date.toRataDie date)) ])

              else
                tr []
                    [ th [ scope "row", class "lr-rowlabel" ] [ text "Cover lost" ]
                    , td [ class "lr-unrostered-row", colspan (List.length request.dates) ] [ text "Not rostered yet for these days." ]
                    ]
            ]
        ]


viewOwnDay : Model -> T.LeaveRequestOut -> Dict Int T.LeaveOut -> Date -> List (Html Msg)
viewOwnDay model request asked date =
    let
        d =
            Date.toRataDie date

        shifts =
            List.filter (\s -> Date.toRataDie s.date == d) request.shifts

        leaves =
            (Dict.get d asked |> Maybe.map List.singleton |> Maybe.withDefault [])
                ++ List.filter (\l -> Date.toRataDie l.date == d) request.other_leave

        leaveChip leave =
            let
                choice =
                    choiceFor model.flags.leaveTypes (T.leaveTypeToString leave.type_)

                state =
                    leaveState leave
            in
            span [ class (leaveChipClass state leave), title (leaveName choice ++ portionLabel leave ++ ", " ++ leaveStateName state) ]
                (leaveChipContent choice state leave)

        shiftChip shift =
            let
                choice =
                    choiceFor model.flags.shiftTypes (T.shiftTypeToString shift.type_)
            in
            span [ class ("re-chip re-shift is-" ++ String.toLower (T.shiftTypeToString shift.type_)), title choice.label ] [ text choice.short ]
    in
    if List.isEmpty shifts && List.isEmpty leaves then
        []

    else
        [ div [ class "lr-chips" ] (List.map shiftChip shifts ++ List.map leaveChip leaves) ]


{-| One approver's decision on one day: approve and decline toggles for someone who can make it, the
decision in words for someone who can't, with who made it.
-}
viewDecision : Model -> T.LeaveRequestOut -> Int -> Int -> String -> String -> Bool -> T.LeaveOut -> Html Msg
viewDecision model request row index approver who canChange leave =
    let
        current =
            decisionOf approver leave

        by =
            decidedLine model.zone approver leave

        saving =
            Set.member leave.id model.saving

        toggleButton offset value icon verb variant =
            let
                on_ =
                    current == value
            in
            button
                ([ type_ "button"
                 , class ("lr-toggle " ++ variant)
                 , classList [ ( "is-on", on_ ) ]
                 , attribute "aria-pressed" (boolString on_)
                 , attribute "aria-label" (verb ++ " " ++ Date.format "EEE d MMM" leave.date ++ " as " ++ who)
                 , title
                    (if on_ then
                        by

                     else
                        verb
                    )
                 , disabled saving
                 , onClick
                    (Decide False
                        { key = requestKey request
                        , approver = approver
                        , leaves = [ leave ]
                        , decision =
                            if on_ then
                                Nothing

                            else
                                value
                        }
                    )
                 ]
                    ++ spotAttributes model request ( row, index * 2 + offset )
                )
                [ i [ class ("bi " ++ icon), attribute "aria-hidden" "true" ] [] ]
    in
    if canChange && not leave.cancelled then
        div [ class "lr-decision", classList [ ( "is-saving", saving ) ] ]
            [ toggleButton 0 (Just True) "bi-check-lg" "Approve" "is-approve"
            , toggleButton 1 (Just False) "bi-x-lg" "Decline" "is-decline"
            ]

    else
        case current of
            Just True ->
                span [ class "lr-state is-approved" ]
                    [ i [ class "bi bi-check-lg", attribute "aria-hidden" "true" ] []
                    , text "Approved"
                    , span [ class "lr-by" ] [ text (decidedBy approver leave) ]
                    ]

            Just False ->
                span [ class "lr-state is-declined" ]
                    [ i [ class "bi bi-x-lg", attribute "aria-hidden" "true" ] []
                    , text "Declined"
                    , span [ class "lr-by" ] [ text (decidedBy approver leave) ]
                    ]

            Nothing ->
                span [ class "lr-state" ] [ text "Waiting" ]


{-| "Approved by Az, 7 Oct 2026, 16:21"
-}
decidedLine : Time.Zone -> String -> T.LeaveOut -> String
decidedLine zone approver leave =
    let
        ( by, at ) =
            if approver == "reg" then
                ( nullable leave.reg_decided_by, nullable leave.reg_decided_at )

            else
                ( nullable leave.dot_decided_by, nullable leave.dot_decided_at )

        verb =
            case decisionOf approver leave of
                Just True ->
                    "Approved"

                Just False ->
                    "Declined"

                Nothing ->
                    "Waiting"
    in
    verb
        ++ (by |> Maybe.map (\name -> " by " ++ name) |> Maybe.withDefault "")
        ++ (at |> Maybe.map (\time -> ", " ++ dateTime zone time) |> Maybe.withDefault "")


{-| Who decided, in a few words: "Az".
-}
decidedBy : String -> T.LeaveOut -> String
decidedBy approver leave =
    (if approver == "reg" then
        nullable leave.reg_decided_by

     else
        nullable leave.dot_decided_by
    )
        |> Maybe.withDefault ""


{-| Everyone on leave that day, this request included, shaded by their share of the roster. Opens the names.
-}
viewAway : Model -> T.LeaveRequestOut -> Int -> Int -> Date -> Html Msg
viewAway model request key index date =
    let
        d =
            Date.toRataDie date

        others =
            List.filter (\a -> Date.toRataDie a.date == d) request.away

        mine =
            List.filter (\l -> Date.toRataDie l.date == d && isActive l) request.leaves

        count =
            awayOn request d

        waiting =
            List.length (List.filter (not << .approved) others) + List.length (List.filter (\l -> leaveState l /= Approved) mine)

        rostered =
            dayInfo request d |> Maybe.map .registrars |> Maybe.withDefault 0

        open =
            model.openDay == Just ( key, d )

        label =
            formatDays count
                ++ " on leave"
                ++ (if rostered > 0 then
                        " of " ++ String.fromInt rostered ++ " on the roster"

                    else
                        ""
                   )
                ++ (if waiting > 0 then
                        ", " ++ String.fromInt waiting ++ " still waiting"

                    else
                        ""
                   )
                ++ " on "
                ++ Date.format "EEE d MMM" date
    in
    button
        ([ type_ "button"
         , class ("lr-heat is-" ++ String.fromInt (heatStep count rostered))
         , classList [ ( "is-open", open ) ]
         , attribute "aria-expanded" (boolString open)
         , attribute "aria-controls" (requestId key ++ "-names")
         , attribute "aria-label" (label ++ ". Show who.")
         , title label
         , onClick (ToggleDay key d)
         ]
            ++ spotAttributes model request ( 2, index * 2 )
        )
        [ text
            (if count == 0 then
                "–"

             else
                formatDays count
            )
        ]


viewDayNames : Model -> Lookups -> T.LeaveRequestOut -> Html Msg
viewDayNames model looks request =
    let
        key =
            requestKey request

        content =
            case model.openDay of
                Just ( k, d ) ->
                    if k /= key then
                        []

                    else
                        let
                            leaveLabel type_ portion approved =
                                (choiceFor model.flags.leaveTypes (T.leaveTypeToString type_)).short
                                    ++ (if portion == "ALL" then
                                            ""

                                        else
                                            "·" ++ String.toLower portion
                                       )
                                    ++ (if approved then
                                            ""

                                        else
                                            ", waiting"
                                       )

                            mine =
                                List.filter (\l -> Date.toRataDie l.date == d && isActive l) request.leaves
                                    |> List.map (\_ -> registrarName looks request.registrar ++ " (this request)")

                            others =
                                request.away
                                    |> List.filter (\a -> Date.toRataDie a.date == d)
                                    |> List.map (\a -> registrarName looks a.registrar ++ " (" ++ leaveLabel a.type_ a.portion a.approved ++ ")")

                            names =
                                mine ++ others
                        in
                        [ strong [] [ text (Date.format "EEE d MMM" (Date.fromRataDie d) ++ ": ") ]
                        , text
                            (if List.isEmpty names then
                                "nobody on leave."

                             else
                                String.join ", " names ++ "."
                            )
                        ]

                Nothing ->
                    []
    in
    div
        [ class "lr-daynames"
        , classList [ ( "is-empty", List.isEmpty content ) ]
        , id (requestId key ++ "-names")
        , attribute "aria-live" "polite"
        ]
        content


{-| The cover the leave would lose that day, and, quieter, the cover already short whatever happens.
-}
viewCover : Model -> Maybe T.RequestDayOut -> Html Msg
viewCover model info =
    case info of
        Just day ->
            if not day.rostered then
                span [ class "lr-unrostered", title "Not rostered yet" ]
                    [ span [ attribute "aria-hidden" "true" ] [ text "–" ]
                    , span [ class "visually-hidden" ] [ text "Not rostered yet" ]
                    ]

            else if List.isEmpty day.lost && List.isEmpty day.short then
                span [ class "visually-hidden" ] [ text "Nothing lost" ]

            else
                let
                    names need =
                        List.map (\t -> (choiceFor model.flags.shiftTypes (T.shiftTypeToString t)).short) need |> String.join "/"

                    full need =
                        List.map (shiftName model) need |> String.join " or "
                in
                div [ class "lr-chips" ]
                    (List.map
                        (\need ->
                            span [ class "lr-gap", title (full need ++ ": nobody else is rostered, so the leave loses it") ]
                                [ i [ class "bi bi-exclamation-diamond-fill", attribute "aria-hidden" "true" ] []
                                , text (names need)
                                , span [ class "visually-hidden" ] [ text " lost" ]
                                ]
                        )
                        day.lost
                        ++ List.map
                            (\need ->
                                span [ class "lr-short", title (full need ++ ": already short before this leave") ]
                                    [ text (names need)
                                    , span [ class "visually-hidden" ] [ text " already short" ]
                                    ]
                            )
                            day.short
                    )

        Nothing ->
            text ""



-- HELPERS


nullable : Nullable a -> Maybe a
nullable value =
    case value of
        Present a ->
            Just a

        Null ->
            Nothing


unique : List comparable -> List comparable
unique items =
    List.foldl
        (\item ( seen, acc ) ->
            if Set.member item seen then
                ( seen, acc )

            else
                ( Set.insert item seen, acc ++ [ item ] )
        )
        ( Set.empty, [] )
        items
        |> Tuple.second


indexOf : a -> List a -> Maybe Int
indexOf item items =
    items
        |> List.indexedMap Tuple.pair
        |> List.filter (\( _, x ) -> x == item)
        |> List.head
        |> Maybe.map Tuple.first


boolString : Bool -> String
boolString b =
    if b then
        "true"

    else
        "false"


plural : Int -> String -> String -> String
plural n one many =
    String.fromInt n
        ++ " "
        ++ (if n == 1 then
                one

            else
                many
           )


isWeekend : Date -> Bool
isWeekend date =
    Date.weekdayNumber date >= 6


{-| "Mon 12 – Fri 16 Oct 2026", "Mon 28 Sep – Fri 2 Oct 2026", "Fri 16 Oct 2026"
-}
spanLabel : List Date -> String
spanLabel dates =
    case ( List.head dates, List.head (List.reverse dates) ) of
        ( Just first, Just last ) ->
            if first == last then
                Date.format "EEE d MMM y" first

            else if Date.year first /= Date.year last then
                Date.format "EEE d MMM y" first ++ " – " ++ Date.format "EEE d MMM y" last

            else if Date.month first /= Date.month last then
                Date.format "EEE d MMM" first ++ " – " ++ Date.format "EEE d MMM y" last

            else
                Date.format "EEE d" first ++ " – " ++ Date.format "EEE d MMM y" last

        _ ->
            ""


{-| "7 Oct 2026, 16:21", in the browser's time zone.
-}
dateTime : Time.Zone -> Time.Posix -> String
dateTime zone posix =
    Date.format "d MMM y" (Date.fromPosix zone posix)
        ++ ", "
        ++ String.padLeft 2 '0' (String.fromInt (Time.toHour zone posix))
        ++ ":"
        ++ String.padLeft 2 '0' (String.fromInt (Time.toMinute zone posix))
